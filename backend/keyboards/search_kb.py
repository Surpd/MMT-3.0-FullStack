from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

def get_search_results_kb(results: list, page: int):
    kb = InlineKeyboardBuilder()
    
    for item in results:
        # Твоя логика иконок теперь живет здесь!
        icon = "🎬" if item.media_type == "movie" else "📺"
        
        kb.row(InlineKeyboardButton(
            text=f"{icon} {item.title} ({item.year})",
            callback_data=f"movie_{item.movie_id}_{item.media_type}"
        ))
    
    # Кнопка пагинации
    kb.row(InlineKeyboardButton(
        text="➕ Ещё варианты", 
        callback_data=f"search_page_{page + 1}"
    ))
    
    return kb.as_markup()
