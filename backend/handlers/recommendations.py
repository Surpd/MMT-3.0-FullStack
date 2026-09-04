from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import db, recommendation_service
from keyboards.recs_kb import recs_card_keyboard
from services.bot_recs_service import get_bot_recommendations_batch
from services.media_state_service import apply_media_state
from services.telegram_ui import parse_callback
from services.ui import render_and_send_card
from utils.states import FilterState, RecsState

router = Router()


def _filters_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🎬 Фильмы", callback_data="rf:type:movie"), InlineKeyboardButton(text="📺 Сериалы", callback_data="rf:type:tv"))
    kb.row(InlineKeyboardButton(text="🎬 + 📺 Всё", callback_data="rf:type:mix"))
    kb.row(*[InlineKeyboardButton(text=f"⭐ {value}", callback_data=f"rf:rating:{value}") for value in ("6", "7", "7.5", "8", "8.5")])
    kb.row(InlineKeyboardButton(text="📅 Мин. год", callback_data="rf:minyear:set"), InlineKeyboardButton(text="📅 Макс. год", callback_data="rf:maxyear:set"))
    kb.row(InlineKeyboardButton(text="🎬 Показать рекомендации", callback_data="rec:generate"))
    return kb.as_markup()


async def _generate(message: Message, state: FSMContext, *, edit_message=None):
    data = await state.get_data()
    movies = await get_bot_recommendations_batch(
        recommendation_service, message.from_user.id, batch_size=5,
        target_type=data.get("target_type", "mix"), min_year=data.get("min_year"),
        max_year=data.get("max_year"), min_rating=data.get("min_rating"),
    )
    if not movies:
        text = "🤷‍♂️ По этим фильтрам ничего не найдено. Ограничения сохранены — попробуйте расширить диапазон."
        if edit_message:
            await edit_message.edit_text(text, reply_markup=_filters_keyboard())
        else:
            await message.answer(text, reply_markup=_filters_keyboard())
        return
    await state.update_data(recs_batch=movies, current_idx=0)
    await state.set_state(RecsState.viewing_recs)
    first = movies[0]
    await render_and_send_card(message.chat.id, first.get("movie_id") or first.get("id"), message.from_user.id, media_type=first.get("media_type", "movie"), is_recs_mode=True, rec_index=0, rec_total=len(movies), edit_message=edit_message)


@router.message(Command("recommend"))
@router.message(F.text.in_({"🎬 Рекомендации", "🎲 Что посмотреть?"}))
async def cmd_recs_start(message: Message, state: FSMContext):
    wait_msg = await message.answer("🧠 Подбираю рекомендации по твоему вкусу...")
    await _generate(message, state)
    try:
        await wait_msg.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("rec:"))
async def cb_recommendation_navigation(callback: CallbackQuery, state: FSMContext):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Карточка устарела", show_alert=True)
        return
    command = action.args[0]
    if command == "filters":
        await callback.answer()
        await state.set_state(FilterState.editing)
        await callback.message.edit_reply_markup(reply_markup=_filters_keyboard())
        return
    if command == "generate":
        await callback.answer("Обновляю...")
        await _generate(callback.message, state, edit_message=callback.message)
        return
    if command == "nav":
        data = await state.get_data()
        movies = data.get("recs_batch", [])
        index = int(action.args[1])
        if not 0 <= index < len(movies):
            await callback.answer("Больше карточек нет", show_alert=True)
            return
        await callback.answer()
        await state.update_data(current_idx=index)
        item = movies[index]
        await render_and_send_card(callback.message.chat.id, item.get("movie_id") or item.get("id"), callback.from_user.id, media_type=item.get("media_type", "movie"), is_recs_mode=True, rec_index=index, rec_total=len(movies), edit_message=callback.message)


@router.callback_query(F.data.startswith("recact:"))
async def cb_recommendation_action(callback: CallbackQuery, state: FSMContext):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректное действие", show_alert=True)
        return
    status, media_type, raw_id = action.args
    try:
        await apply_media_state(db, recommendation_service, callback.from_user.id, int(raw_id), media_type, status)
    except Exception:
        await callback.answer("Не удалось сохранить действие. Попробуйте ещё раз.", show_alert=True)
        return
    data = await state.get_data()
    movies = data.get("recs_batch", [])
    next_index = int(data.get("current_idx", 0)) + 1
    await callback.answer("Сохранено")
    if next_index < len(movies):
        await state.update_data(current_idx=next_index)
        item = movies[next_index]
        await render_and_send_card(callback.message.chat.id, item.get("movie_id") or item.get("id"), callback.from_user.id, media_type=item.get("media_type", "movie"), is_recs_mode=True, rec_index=next_index, rec_total=len(movies), edit_message=callback.message)
    else:
        await callback.message.edit_text("✅ Подборка закончилась.", reply_markup=InlineKeyboardBuilder().button(text="🔄 Ещё рекомендации", callback_data="rec:generate").as_markup())


@router.callback_query(FilterState.editing, F.data.startswith("rf:"))
async def cb_recommendation_filter(callback: CallbackQuery, state: FSMContext):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректный фильтр", show_alert=True)
        return
    kind, value = action.args
    if value == "set":
        await state.set_state(FilterState.waiting_min_year if kind == "minyear" else FilterState.waiting_max_year)
        await callback.answer()
        await callback.message.edit_text("Введите год числом от 1888 до 2100. Для отмены — /start.")
        return
    update = {"target_type": value} if kind == "type" else {"min_rating": float(value)}
    await state.update_data(**update)
    await callback.answer("Фильтр сохранён")
    await callback.message.edit_reply_markup(reply_markup=_filters_keyboard())


async def _save_year(message: Message, state: FSMContext, key: str):
    try:
        year = int((message.text or "").strip())
    except ValueError:
        await message.answer("Нужен год числом, например 2000.")
        return
    if not 1888 <= year <= 2100:
        await message.answer("Год должен быть от 1888 до 2100.")
        return
    data = await state.get_data()
    if key == "min_year" and data.get("max_year") is not None and year > data["max_year"]:
        await message.answer("Минимальный год не может быть больше максимального.")
        return
    if key == "max_year" and data.get("min_year") is not None and year < data["min_year"]:
        await message.answer("Максимальный год не может быть меньше минимального.")
        return
    await state.update_data(**{key: year})
    await state.set_state(FilterState.editing)
    await message.answer("Фильтр сохранён. Нажмите ⚙️ Фильтры в карточке рекомендаций или /recommend.", reply_markup=_filters_keyboard())


@router.message(FilterState.waiting_min_year, F.text)
async def min_year(message: Message, state: FSMContext):
    await _save_year(message, state, "min_year")


@router.message(FilterState.waiting_max_year, F.text)
async def max_year(message: Message, state: FSMContext):
    await _save_year(message, state, "max_year")
