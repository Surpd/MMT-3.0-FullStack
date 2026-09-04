import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.types.web_app_info import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import WEBAPP_URL, db
from services.media_state_service import apply_media_state
from services.telegram_ui import parse_callback
from services.tv_service import get_tv_progress, get_tv_progress_summaries, set_episode_watched

router = Router()


def _series_menu():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="▶️ Продолжить смотреть", callback_data="series:continue"))
    kb.row(InlineKeyboardButton(text="📺 Мои сериалы", callback_data="series:all"))
    return kb.as_markup()


async def _tv_ids(user_id: int) -> list[int]:
    ids = set()
    for status in ("liked", "watchlist"):
        for row in await db.get_user_media_by_status(user_id, status):
            if (row.get("media_type") or "movie") == "tv" and row.get("movie_id") is not None:
                ids.add(int(row["movie_id"]))
    return list(ids)


async def _show_series(message: Message, *, continue_only: bool = False, edit_message=None):
    try:
        tv_ids = await _tv_ids(message.from_user.id)
    except Exception:
        text = "Не удалось загрузить сериалы. Попробуйте ещё раз."
        if edit_message:
            await edit_message.edit_text(text, reply_markup=_series_menu())
        else:
            await message.answer(text, reply_markup=_series_menu())
        return
    if not tv_ids:
        text = "📺 Сериалов пока нет. Найдите сериал через 🔎 Найти и добавьте его в планы."
        if edit_message:
            await edit_message.edit_text(text, reply_markup=_series_menu())
        else:
            await message.answer(text, reply_markup=_series_menu())
        return
    try:
        summaries = await get_tv_progress_summaries(message.from_user.id, tv_ids, ensure_metadata=False)
    except Exception:
        text = "Не удалось загрузить прогресс сериалов. Попробуйте ещё раз."
        if edit_message:
            await edit_message.edit_text(text, reply_markup=_series_menu())
        else:
            await message.answer(text, reply_markup=_series_menu())
        return
    if continue_only:
        tv_ids = [tv_id for tv_id in tv_ids if summaries.get(tv_id, {}).get("state") == "watching"]
    if not tv_ids:
        text = "▶️ Сейчас нечего продолжать. Все доступные серии отмечены или прогресс ещё не начат."
        markup = _series_menu()
    else:
        text = "📺 <b>Сериалы</b>\n"
        markup_builder = InlineKeyboardBuilder()
        for tv_id in tv_ids[:10]:
            summary = summaries.get(tv_id) or {}
            next_ep = summary.get("next_episode") or {}
            ep_label = f"S{int(next_ep.get('season_number', 0)):02d}E{int(next_ep.get('episode_number', 0)):02d}" if next_ep else "прогресс не начат"
            text += f"\n📺 {tv_id} · {ep_label} · {summary.get('watched_episodes', 0)}/{summary.get('available_episodes', 0)}"
            markup_builder.row(InlineKeyboardButton(text=f"📺 Открыть {tv_id} · {ep_label}", callback_data=f"tv:{tv_id}"))
        markup_builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="series:menu"))
        markup = markup_builder.as_markup()
    if edit_message:
        await edit_message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.message(Command("series"))
@router.message(F.text == "📺 Сериалы")
async def cmd_series(message: Message, state: FSMContext):
    await state.clear()
    await _show_series(message)


@router.callback_query(F.data.startswith("series:"))
async def series_menu(callback: CallbackQuery):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректный экран", show_alert=True)
        return
    await callback.answer()
    command = action.args[0]
    if command == "menu":
        await callback.message.edit_text("📺 <b>Сериалы</b>", reply_markup=_series_menu(), parse_mode="HTML")
    else:
        await _show_series(callback.message, continue_only=command == "continue", edit_message=callback.message)


def _progress_keyboard(tv_id: int, progress: dict):
    kb = InlineKeyboardBuilder()
    next_ep = progress.get("next_episode") or {}
    if next_ep:
        s, e = int(next_ep.get("season_number", 0)), int(next_ep.get("episode_number", 0))
        kb.button(text="✅ Серия просмотрена", callback_data=f"ep:{tv_id}:{s}:{e}:1")
        kb.button(text="⏭ Следующая", callback_data=f"ep:{tv_id}:{s}:{e}:1")
    for season in (progress.get("seasons") or [])[:8]:
        number = season.get("season_number")
        if number and number > 0:
            kb.button(text=f"📋 Сезон {number}", callback_data=f"season:{tv_id}:{number}")
    kb.button(text="🔔 Подписка" if not progress.get("notification_enabled") else "🔕 Отписаться", callback_data=f"sub:{tv_id}")
    kb.button(text="🌐 Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))
    kb.button(text="⬅️ К сериалам", callback_data="series:menu")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


async def _show_progress(callback: CallbackQuery, tv_id: int):
    try:
        progress = await get_tv_progress(callback.from_user.id, tv_id)
    except Exception:
        await callback.message.edit_text("Не удалось получить прогресс сериала. Попробуйте ещё раз.", reply_markup=_series_menu())
        return
    next_ep = progress.get("next_episode") or {}
    if next_ep:
        episode_label = f"S{int(next_ep.get('season_number', 0)):02d}E{int(next_ep.get('episode_number', 0)):02d}"
        episode_title = html.escape(str(next_ep.get("name") or "Без названия"))
        next_text = f"\n▶️ Следующая: <b>{episode_label}</b> · {episode_title}"
    else:
        next_text = "\n✅ Нет непросмотренных доступных серий."
    text = f"📺 <b>Сериал {tv_id}</b>\nПрогресс: {progress.get('watched_episodes', 0)}/{progress.get('available_episodes', 0)}{next_text}"
    await callback.message.edit_text(text, reply_markup=_progress_keyboard(tv_id, progress), parse_mode="HTML")


@router.callback_query(F.data.startswith("tv:"))
async def tv_progress(callback: CallbackQuery):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Карточка сериала устарела", show_alert=True)
        return
    await callback.answer()
    await _show_progress(callback, int(action.args[1]))


@router.callback_query(F.data.startswith("ep:"))
async def episode_action(callback: CallbackQuery):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректная серия", show_alert=True)
        return
    tv_id, season, episode, watched = map(int, action.args)
    try:
        await set_episode_watched(callback.from_user.id, tv_id, season, episode, bool(watched))
        await callback.answer("Прогресс обновлён")
        await _show_progress(callback, tv_id)
    except ValueError:
        await callback.answer("Эта серия ещё недоступна", show_alert=True)
    except Exception:
        await callback.answer("Не удалось обновить прогресс", show_alert=True)


@router.callback_query(F.data.startswith("sub:"))
async def subscription_action(callback: CallbackQuery):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректная подписка", show_alert=True)
        return
    tv_id = int(action.args[0])
    try:
        progress = await get_tv_progress(callback.from_user.id, tv_id)
        enabled = not bool(progress.get("notification_enabled"))
        await db.set_tv_notification_subscription(callback.from_user.id, tv_id, enabled)
    except Exception:
        await callback.answer("Не удалось обновить подписку. Попробуйте ещё раз.", show_alert=True)
        return
    await callback.answer("Подписка обновлена")
    await _show_progress(callback, tv_id)
