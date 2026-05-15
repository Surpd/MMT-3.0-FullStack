from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder



def recommendations_keyboard(
    items: list[tuple[int, str, str]], 
    parent_movie_id: int, 
    offset: int, 
    has_more: bool, 
    media_type: str = "movie"
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    
    # Чтобы не путать с аргументом функции, назовем тип элемента rec_media_type
    for rec_movie_id, title, rec_media_type in items:
        icon = "🎬" if rec_media_type == "movie" else "📺"
        kb.row(InlineKeyboardButton(text=f"{icon} {title}", callback_data=f"movie_{rec_movie_id}_{rec_media_type}"))
    
    if has_more:
        kb.row(InlineKeyboardButton(text="🔄 Другие варианты", callback_data=f"reroll_{media_type}_{parent_movie_id}_{offset + 3}"))
    
    return kb.as_markup()
