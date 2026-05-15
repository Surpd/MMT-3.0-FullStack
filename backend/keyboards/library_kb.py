from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def library_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⏳ Хочу", callback_data="showlist_watchlist_0"))
    kb.row(InlineKeyboardButton(text="✅ Видел", callback_data="showlist_liked_0"))
    kb.row(InlineKeyboardButton(text="🗑 Архив", callback_data="showlist_archive_0"))
    
    return kb.as_markup()

def library_list_keyboard(status: str, page: int, page_size: int, total: int, items: list[tuple[int, str, str, int | None]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    
    # Собираем фильмы в кучу (и сразу пришиваем "хлебные крошки" для возврата)
    for movie_id, title, media_type, rating in items:
        icon = "🎬" if media_type == "movie" else "📺"
        btn_text = f"{icon} {title} ⭐️ {rating}" if rating else f"{icon} {title}"
        
        # Вот она, 9-я строка: передаем status и page, чтобы карточка знала, куда возвращаться
        kb.button(text=btn_text, callback_data=f"movie_{movie_id}_{media_type}_{status}_{page}")

    # Выстраиваем собранные фильмы по 2 в ряд
    kb.adjust(2)

    # Пульт навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"showlist_{status}_{page - 1}"))
    
    current_page = page + 1
    total_pages = (total + page_size - 1) // page_size
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"Стр {current_page}/{total_pages}", callback_data="ignore"))
        
    if (page + 1) * page_size < total:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"showlist_{status}_{page + 1}"))
        
    if nav_buttons:
        kb.row(*nav_buttons)

    # Возврат в главное меню категорий
    kb.row(InlineKeyboardButton(text="🔙 К категориям", callback_data="main_menu_back"))
    
    return kb.as_markup()