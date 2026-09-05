from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def profile_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔔 Отслеживаемые сериалы", callback_data="tracked:1"))
    return kb.as_markup()


def tracked_series_keyboard(items: list[dict], page: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in items:
        tv_id = int(item["tv_id"])
        title = str(item.get("title") or f"Сериал {tv_id}")[:35]
        watched = int(item.get("watched_episodes") or 0)
        available = int(item.get("available_episodes") or 0)
        progress = f"{watched}/{available}" if available else "н/д"
        kb.row(InlineKeyboardButton(text=f"📺 {title} · {progress}", callback_data=f"tv:{tv_id}:tracked"))

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"tracked:{page - 1}"))
    total_pages = max(1, (total + page_size - 1) // page_size)
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"tracked:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="⬅️ В профиль", callback_data="profile:menu"))
    return kb.as_markup()
