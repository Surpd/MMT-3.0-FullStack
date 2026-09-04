from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

def get_search_results_kb(results: list, page: int, search_type: str = "movie"):
    kb = InlineKeyboardBuilder()
    
    for item in results:
        # Твоя логика иконок теперь живет здесь!
        media_type = getattr(item, "media_type", None) or item.get("media_type", "movie")
        icon = "🎬" if media_type == "movie" else "📺"
        
        title = getattr(item, "title", None) or item.get("title") or item.get("name", "Без названия")
        year = getattr(item, "year", None) or item.get("year", "н/д")
        movie_id = getattr(item, "movie_id", None) or item.get("id")
        kb.row(InlineKeyboardButton(text=f"{icon} {title} ({year})", callback_data=f"sm:{media_type}:{movie_id}"))
    
    navigation = []
    if page > 1:
        navigation.append(InlineKeyboardButton(text="⬅️", callback_data=f"s:{search_type}:{page - 1}"))
    navigation.append(InlineKeyboardButton(text="➡️", callback_data=f"s:{search_type}:{page + 1}"))
    kb.row(*navigation)
    
    return kb.as_markup()


def search_type_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎬 Фильм", callback_data="searchtype:movie")
    kb.button(text="📺 Сериал", callback_data="searchtype:tv")
    kb.button(text="👤 Актёр / режиссёр", callback_data="searchtype:person")
    kb.adjust(1)
    return kb.as_markup()


def unified_results_keyboard(results: list, page: int):
    kb = InlineKeyboardBuilder()
    for item in results:
        if isinstance(item, dict) and item.get("media_type") == "person":
            department = item.get("known_for_department") or "Кино"
            kb.row(InlineKeyboardButton(
                text=f"👤 {item.get('name', 'Без имени')} · {department}",
                callback_data=f"person:{item.get('id')}",
            ))
            continue
        media_type = getattr(item, "media_type", None) or item.get("media_type", "movie")
        icon = "🎬" if media_type == "movie" else "📺"
        title = getattr(item, "title", None) or item.get("title") or item.get("name", "Без названия")
        year = getattr(item, "year", None) or item.get("year", "н/д")
        movie_id = getattr(item, "movie_id", None) or item.get("id")
        kb.row(InlineKeyboardButton(text=f"{icon} {title} ({year})", callback_data=f"sm:{media_type}:{movie_id}"))
    navigation = []
    if page > 1:
        navigation.append(InlineKeyboardButton(text="⬅️", callback_data=f"s:all:{page - 1}"))
    navigation.append(InlineKeyboardButton(text="➡️", callback_data=f"s:all:{page + 1}"))
    kb.row(*navigation)
    return kb.as_markup()


def person_results_keyboard(results: list[dict], page: int):
    kb = InlineKeyboardBuilder()
    for person in results:
        department = person.get("known_for_department") or "Кино"
        kb.row(InlineKeyboardButton(text=f"👤 {person.get('name', 'Без имени')} · {department}", callback_data=f"person:{person.get('id')}"))
    navigation = []
    if page > 1:
        navigation.append(InlineKeyboardButton(text="⬅️", callback_data=f"s:person:{page - 1}"))
    navigation.append(InlineKeyboardButton(text="➡️", callback_data=f"s:person:{page + 1}"))
    kb.row(*navigation)
    return kb.as_markup()


def empty_search_keyboard(search_type: str, page: int):
    kb = InlineKeyboardBuilder()
    if page > 1:
        kb.button(text="⬅️ Назад к результатам", callback_data=f"s:{search_type}:{page - 1}")
    else:
        kb.button(text="🔎 Новый поиск", callback_data="searchtype:all")
    return kb.as_markup()
