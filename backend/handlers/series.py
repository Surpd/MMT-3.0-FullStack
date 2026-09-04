import html
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.types.web_app_info import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import WEBAPP_URL, db
from services.media_state_service import apply_media_state
from services.telegram_ui import parse_callback
from services.tv_service import get_tv_progress, get_tv_progress_summaries, get_tv_season_progress, set_episode_watched

router = Router()


async def _edit_screen(message: Message, text: str, markup=None) -> None:
    """Edit either a text message or a poster caption without Telegram errors."""
    if getattr(message, "photo", None):
        plain_text = html.unescape(re.sub(r"<[^>]+>", "", text))
        await message.edit_caption(caption=plain_text[:1024], reply_markup=markup)
    else:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML")


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
            await _edit_screen(edit_message, text, _series_menu())
        else:
            await message.answer(text, reply_markup=_series_menu())
        return
    if not tv_ids:
        text = "📺 Сериалов пока нет. Найдите сериал через 🔎 Найти и добавьте его в планы."
        if edit_message:
            await _edit_screen(edit_message, text, _series_menu())
        else:
            await message.answer(text, reply_markup=_series_menu())
        return
    try:
        summaries = await get_tv_progress_summaries(message.from_user.id, tv_ids, ensure_metadata=True)
    except Exception:
        text = "Не удалось загрузить прогресс сериалов. Попробуйте ещё раз."
        if edit_message:
            await _edit_screen(edit_message, text, _series_menu())
        else:
            await message.answer(text, reply_markup=_series_menu())
        return
    if continue_only:
        tv_ids = [tv_id for tv_id in tv_ids if summaries.get(tv_id, {}).get("state") == "watching"]
    if not tv_ids:
        text = "▶️ Сейчас нечего продолжать. Все доступные серии отмечены или прогресс ещё не начат."
        markup = _series_menu()
    else:
        text = "📺 <b>Мои сериалы</b>\n"
        markup_builder = InlineKeyboardBuilder()
        for tv_id in tv_ids[:10]:
            summary = summaries.get(tv_id) or {}
            known = int(summary.get("known_episodes") or 0)
            available = int(summary.get("available_episodes") or 0)
            if not available and not known:
                continue
            title = html.escape(str(summary.get("title") or f"Сериал {tv_id}"))
            next_ep = summary.get("next_episode") or {}
            if next_ep:
                ep_label = f"S{int(next_ep.get('season_number', 0)):02d}E{int(next_ep.get('episode_number', 0)):02d}"
                progress_text = f"▶️ Следующая: {ep_label}"
            elif available:
                progress_text = f"✅ Завершено: {summary.get('watched_episodes', 0)} из {available}"
            else:
                progress_text = f"⏳ Прогресс ещё не начат · доступно серий: {known}"
            text += f"\n\n📺 <b>{title}</b>\n{progress_text}"
            markup_builder.row(InlineKeyboardButton(text=f"📺 {str(summary.get('title') or f'Сериал {tv_id}')[:38]}", callback_data=f"tv:{tv_id}"))
        if text == "📺 <b>Мои сериалы</b>\n":
            text += "\nДанные об эпизодах пока недоступны. Откройте сериал ещё раз позже."
        markup_builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="series:menu"))
        markup = markup_builder.as_markup()
    if edit_message:
        await _edit_screen(edit_message, text, markup)
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
        await _edit_screen(callback.message, "📺 <b>Сериалы</b>", _series_menu())
    else:
        await _show_series(callback.message, continue_only=command == "continue", edit_message=callback.message)


def _progress_keyboard(tv_id: int, progress: dict):
    kb = InlineKeyboardBuilder()
    next_ep = progress.get("next_episode") or {}
    if next_ep:
        s, e = int(next_ep.get("season_number", 0)), int(next_ep.get("episode_number", 0))
        kb.button(text=f"✅ Отметить S{s:02d}E{e:02d}", callback_data=f"ep:{tv_id}:{s}:{e}:1")
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
        await _edit_screen(callback.message, "Не удалось получить прогресс сериала. Попробуйте ещё раз.", _series_menu())
        return
    next_ep = progress.get("next_episode") or {}
    if next_ep:
        episode_label = f"S{int(next_ep.get('season_number', 0)):02d}E{int(next_ep.get('episode_number', 0)):02d}"
        episode_title = html.escape(str(next_ep.get("name") or "Без названия"))
        next_text = f"\n▶️ Следующая: <b>{episode_label}</b> · {episode_title}"
    else:
        next_text = "\n✅ Нет непросмотренных доступных серий."
    available = int(progress.get("available_episodes") or 0)
    known = int(progress.get("known_episodes") or 0)
    if available:
        progress_text = f"{progress.get('watched_episodes', 0)} из {available}"
    elif known:
        progress_text = f"эпизоды загружены частично · всего в каталоге: {known}"
    else:
        progress_text = "список эпизодов пока загружается"
    title = html.escape(str(progress.get("title") or f"Сериал {tv_id}"))
    text = f"📺 <b>{title}</b>\nПрогресс: {progress_text}{next_text}"
    await _edit_screen(callback.message, text, _progress_keyboard(tv_id, progress))


@router.callback_query(F.data.startswith("tv:"))
async def tv_progress(callback: CallbackQuery):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Карточка сериала устарела", show_alert=True)
        return
    await callback.answer()
    await _show_progress(callback, int(action.args[1]))


@router.callback_query(F.data.startswith("season:"))
async def season_action(callback: CallbackQuery):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректный сезон", show_alert=True)
        return
    tv_id, season_number = map(int, action.args)
    try:
        season = await get_tv_season_progress(callback.from_user.id, tv_id, season_number)
    except Exception:
        await callback.answer("Не удалось загрузить эпизоды", show_alert=True)
        return
    if not season:
        await callback.answer("Сезон пока недоступен", show_alert=True)
        return
    await callback.answer()
    title = html.escape(str(season.get("title") or f"Сериал {tv_id}"))
    watched = int(season.get("watched_episode_count") or 0)
    available = int(season.get("available_episode_count") or 0)
    season_progress = f"{watched} из {available}" if available else "данные об эпизодах загружаются"
    text = f"📺 <b>{title}</b>\n📋 <b>Сезон {season_number}</b>\nПрогресс: {season_progress}\n"
    kb = InlineKeyboardBuilder()
    episodes = season.get("episodes") or []
    for episode in episodes[:15]:
        episode_number = int(episode.get("episode_number") or 0)
        if episode_number <= 0:
            continue
        label = f"S{season_number:02d}E{episode_number:02d}"
        name = html.escape(str(episode.get("name") or "Без названия"))
        is_watched = bool(episode.get("watched"))
        text += f"\n{'✅' if is_watched else '▫️'} <b>{label}</b> · {name}"
        kb.row(InlineKeyboardButton(
            text=f"{'↩️ Снять' if is_watched else '✅ Отметить'} {label}",
            callback_data=f"ep:{tv_id}:{season_number}:{episode_number}:{0 if is_watched else 1}",
        ))
    if len(episodes) > 15:
        text += "\n\nПоказаны первые 15 эпизодов."
    kb.row(InlineKeyboardButton(text="⬅️ К сериалу", callback_data=f"tv:{tv_id}"))
    await _edit_screen(callback.message, text, kb.as_markup())


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
