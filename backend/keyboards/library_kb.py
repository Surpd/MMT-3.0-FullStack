from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def library_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🎬 Фильмы", callback_data="lib:liked:0:movie"), InlineKeyboardButton(text="📺 Сериалы", callback_data="lib:liked:0:tv"))
    kb.row(InlineKeyboardButton(text="▶️ Продолжить просмотр", callback_data="series:continue"))
    kb.row(InlineKeyboardButton(text="⭐ Лучшие оценки", callback_data="lib:top:0:all"))
    kb.row(InlineKeyboardButton(text="🕐 Недавно добавленные", callback_data="lib:recent:0:all"))
    kb.row(InlineKeyboardButton(text="🔖 В планах", callback_data="lib:watchlist:0:all"))
    kb.row(InlineKeyboardButton(text="🗑 Не интересно", callback_data="lib:archive:0:all"))
    
    return kb.as_markup()

def library_list_keyboard(status: str, page: int, page_size: int, total: int, items: list[tuple[int, str, str, int | None]], media_type: str = "all") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    
    # Собираем фильмы в кучу (и сразу пришиваем "хлебные крошки" для возврата)
    for movie_id, title, item_media_type, rating in items:
        icon = "🎬" if item_media_type == "movie" else "📺"
        btn_text = f"{icon} {title} ⭐️ {rating}" if rating else f"{icon} {title}"
        
        # Вот она, 9-я строка: передаем status и page, чтобы карточка знала, куда возвращаться
        kb.button(text=btn_text, callback_data=f"libm:{item_media_type}:{movie_id}:{status}:{page}:{media_type}")

    # Выстраиваем собранные фильмы по 2 в ряд
    kb.adjust(2)

    # Пульт навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"lib:{status}:{page - 1}:{media_type}"))
    
    current_page = page + 1
    total_pages = (total + page_size - 1) // page_size
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"Стр {current_page}/{total_pages}", callback_data="ignore"))
        
    if (page + 1) * page_size < total:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"lib:{status}:{page + 1}:{media_type}"))
        
    if nav_buttons:
        kb.row(*nav_buttons)

    # Возврат в главное меню категорий
    kb.row(InlineKeyboardButton(text="🔙 К категориям", callback_data="main_menu_back"))
    
    return kb.as_markup()
