import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import bot, tmdb
from keyboards.search_kb import get_search_results_kb, person_results_keyboard, unified_results_keyboard
from services.search_service import get_person_search_results, get_search_results, get_typed_search_results, get_unified_search_results
from services.telegram_ui import parse_callback
from services.ui import render_and_send_card
from utils.states import SearchState

router = Router()


def _person_credits_keyboard(person_id: int, person_type: str = "movie"):
    kb = InlineKeyboardBuilder()
    kb.button(text="🎬 Фильмы", callback_data=f"credits:{person_id}:movie:1")
    kb.button(text="📺 Сериалы", callback_data=f"credits:{person_id}:tv:1")
    kb.button(text="⬅️ Назад", callback_data="searchtype:person")
    kb.adjust(2, 1)
    return kb.as_markup()


async def _start_search(message: Message, state: FSMContext):
    await state.update_data(search_type="all")
    await state.set_state(SearchState.waiting_query)
    await message.answer("Введите название фильма, сериала, актёра или режиссёра.")


@router.message(Command("search"))
@router.message(F.text.in_({"🔎 Найти", "🔍 Поиск"}))
async def cmd_search(message: Message, state: FSMContext):
    await _start_search(message, state)


@router.callback_query(F.data.startswith("searchtype:"))
async def choose_search_type(callback: CallbackQuery, state: FSMContext):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректный запрос", show_alert=True)
        return
    await state.update_data(search_type=action.args[0])
    await state.set_state(SearchState.waiting_query)
    await callback.answer()
    await callback.message.edit_text("Напишите название или имя одним сообщением.\n\nДля отмены нажмите /start.")


async def _show_results(message: Message, state: FSMContext, query: str, search_type: str, page: int, *, edit_message=None):
    if search_type == "person":
        results, source = await get_person_search_results(query, page)
        markup = person_results_keyboard(results, page) if results else None
        text = f"{source} · Люди: <i>{html.escape(query)}</i> · стр. {page}"
    elif search_type in {"movie", "tv"}:
        results, source = await get_typed_search_results(query, search_type, page)
        markup = get_search_results_kb(results, page) if results else None
        text = f"{source} · {'Фильмы' if search_type == 'movie' else 'Сериалы'}: <i>{html.escape(query)}</i> · стр. {page}"
    elif search_type == "all":
        results, source = await get_unified_search_results(query, page)
        markup = unified_results_keyboard(results, page) if results else None
        text = f"{source} · Фильмы, сериалы и люди: <i>{html.escape(query)}</i> · стр. {page}"
    else:
        results, source = await get_search_results(query, page=page)
        markup = get_search_results_kb(results, page) if results else None
        text = f"{source} · <i>{html.escape(query)}</i> · стр. {page}"

    if not results:
        text = "Ничего не найдено. Попробуйте другой запрос."
    if edit_message:
        await edit_message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.message(SearchState.waiting_query, F.text)
async def handle_typed_search(message: Message, state: FSMContext):
    query = (message.text or "").strip()
    if not query or len(query) > 100:
        await message.answer("Запрос должен быть от 1 до 100 символов.")
        return
    data = await state.get_data()
    search_type = data.get("search_type", "all")
    await state.update_data(current_query=query, search_type=search_type)
    await _show_results(message, state, query, search_type, 1)


@router.message(F.text, ~F.text.startswith("/"))
async def handle_legacy_free_text_search(message: Message, state: FSMContext):
    """Keep the old free-text search entry point for existing users."""
    if message.text in {"🎬 Рекомендации", "📚 Моё", "🔖 В планах", "📺 Сериалы", "📊 Профиль", "🌐 Открыть приложение", "🧠 Квиз"}:
        return
    query = (message.text or "").strip()
    if not query:
        return
    await state.update_data(current_query=query, search_type="all")
    await _show_results(message, state, query, "all", 1)


@router.callback_query(F.data.startswith("s:"))
async def search_page(callback: CallbackQuery, state: FSMContext):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректная страница", show_alert=True)
        return
    data = await state.get_data()
    query = data.get("current_query")
    if not query:
        await callback.answer("Поиск потерян. Начните заново через 🔎 Найти.", show_alert=True)
        return
    await callback.answer()
    await _show_results(callback.message, state, query, action.args[0], int(action.args[1]), edit_message=callback.message)


@router.callback_query(F.data.startswith("search_page_"))
async def legacy_search_page(callback: CallbackQuery, state: FSMContext):
    raw_page = (callback.data or "").removeprefix("search_page_")
    if not raw_page.isdecimal() or not 1 <= int(raw_page) <= 100:
        await callback.answer("Некорректная страница", show_alert=True)
        return
    data = await state.get_data()
    query = data.get("current_query")
    if not query:
        await callback.answer("Поиск потерян. Начните заново через 🔎 Найти.", show_alert=True)
        return
    await callback.answer()
    await _show_results(callback.message, state, query, data.get("search_type", "movie"), int(raw_page), edit_message=callback.message)


@router.callback_query(F.data.startswith("m:"))
async def select_search_media(callback: CallbackQuery, state: FSMContext):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректный фильм", show_alert=True)
        return
    await callback.answer()
    media_type, raw_id = action.args
    data = await state.get_data()
    await render_and_send_card(callback.message.chat.id, int(raw_id), callback.from_user.id, media_type=media_type, edit_message=callback.message, back_data=f"s:{data.get('search_type', media_type)}:1")


@router.callback_query(F.data.startswith("person:"))
async def select_person(callback: CallbackQuery, state: FSMContext):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректный человек", show_alert=True)
        return
    await callback.answer()
    credits = await tmdb.get_person_credits(int(action.args[0]))
    name = html.escape((await state.get_data()).get("current_query", "Человек"))
    text = f"👤 <b>{name}</b>\n\n🎬 Популярные работы:"
    items = []
    for item in sorted((credits.get("cast") or []) + (credits.get("crew") or []), key=lambda row: row.get("popularity", 0), reverse=True):
        media_type = item.get("media_type")
        if media_type not in {"movie", "tv"} or item.get("id") is None:
            continue
        title = item.get("title") or item.get("name") or "Без названия"
        if (item.get("id"), media_type) in items:
            continue
        items.append((item.get("id"), media_type))
        text += f"\n{len(items)}. {html.escape(str(title))}"
        if len(items) >= 5:
            break
    await state.update_data(person_id=action.args[0], person_name=name)
    await callback.message.edit_text(text[:4000] if len(items) else "У этого человека пока нет доступных работ.", reply_markup=_person_credits_keyboard(int(action.args[0])), parse_mode="HTML")


@router.callback_query(F.data.startswith("credits:"))
async def person_credits(callback: CallbackQuery, state: FSMContext):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректный список", show_alert=True)
        return
    person_id, media_type, page = action.args
    credits = await tmdb.get_person_credits(int(person_id))
    rows = [item for item in credits.get("cast", []) + credits.get("crew", []) if item.get("media_type") == media_type and item.get("id") is not None]
    page_number = int(page)
    page_rows = rows[(page_number - 1) * 5:page_number * 5]
    if not page_rows:
        await callback.answer("Больше работ нет", show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    for item in page_rows:
        title = item.get("title") or item.get("name") or "Без названия"
        kb.row(InlineKeyboardButton(text=f"{'🎬' if media_type == 'movie' else '📺'} {title}", callback_data=f"m:{media_type}:{item['id']}"))
    if page_number > 1:
        kb.button(text="⬅️", callback_data=f"credits:{person_id}:{media_type}:{page_number - 1}")
    if page_number * 5 < len(rows):
        kb.button(text="➡️", callback_data=f"credits:{person_id}:{media_type}:{page_number + 1}")
    kb.row(InlineKeyboardButton(text="⬅️ К человеку", callback_data=f"person:{person_id}"))
    await callback.answer()
    await callback.message.edit_text(f"👤 Работы · {'фильмы' if media_type == 'movie' else 'сериалы'} · стр. {page_number}", reply_markup=kb.as_markup())
