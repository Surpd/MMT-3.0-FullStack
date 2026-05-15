from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# details_btn_text по умолчанию равен "ℹ️ Детали", поэтому кнопка не пропала
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

def movie_card_keyboard(movie_id, user_status, media_type="movie", user_rating=None, back_data=None, details_btn_text="ℹ️ Детали", is_full: bool = False):
    builder = InlineKeyboardBuilder()
    
    # 1. ВОТ ТЕ САМЫЕ КНОПКИ (теперь их две, добавляем просто как кнопки)
    if is_full:
        builder.button(text="⬅️ Свернуть", callback_data=f"collapse_{media_type}_{movie_id}_{back_data or 'none'}")
        builder.button(text="🔮 Похожие", callback_data=f"similar_{media_type}_{movie_id}")
    else:
        builder.button(text="ℹ️ Детали", callback_data=f"expand_{media_type}_{movie_id}_{back_data or 'none'}")
        builder.button(text="🔮 Похожие", callback_data=f"similar_{media_type}_{movie_id}")

    # 2. Логика статусов и рейтинга
    if user_status == "none":
        builder.button(text="⏳ Хочу", callback_data=f"status_watchlist_{movie_id}_{media_type}")
        builder.button(text="✅ Видел", callback_data=f"status_liked_{movie_id}_{media_type}")
        builder.button(text="🗑 Архив", callback_data=f"status_archive_{movie_id}_{media_type}")
        # 1 ряд: 2 кнопки (Детали, Похожие)
        # 2 ряд: 2 кнопки (Хочу, Видел)
        # 3 ряд: 1 кнопка (Архив)
        builder.adjust(2, 3) 

    elif user_status == "watchlist":
        builder.button(text="✅ Видел", callback_data=f"status_liked_{movie_id}_{media_type}")
        builder.button(text="🗑 В архив", callback_data=f"status_archive_{movie_id}_{media_type}")
        builder.button(text="🔄 Убрать", callback_data=f"status_none_{movie_id}_{media_type}")
        # 1 ряд: 2 кнопки (Детали, Похожие)
        # 2 ряд: 2 кнопки (Видел, В архив)
        # 3 ряд: 1 кнопка (Убрать)
        builder.adjust(2, 3) 

    elif user_status == "liked":
        # Звезды рейтинга
        for i in range(1, 6):
            text = f"✅ {i}" if user_rating == i else f"⭐ {i}"
            builder.button(text=text, callback_data=f"rate_{movie_id}_{i}")
        
        builder.button(text="⏳ В планы", callback_data=f"status_watchlist_{movie_id}_{media_type}")
        builder.button(text="🗑 В архив", callback_data=f"status_archive_{movie_id}_{media_type}")
        # 1 ряд: 2 кнопки (Детали, Похожие)
        # 2 ряд: 5 звезд
        # 3 ряд: 2 кнопки (В планы, В архив)
        builder.adjust(2, 5, 2) 

    elif user_status == "archive":
        builder.button(text="🔄 Вернуть", callback_data=f"status_none_{movie_id}_{media_type}")
        # 1 ряд: 2 кнопки (Детали, Похожие)
        # 2 ряд: 1 кнопка (Вернуть)
        builder.adjust(2, 1)

    # 3. Кнопка возврата (добавляется через row, так как она идет ПОСЛЕ adjust)
    if back_data and back_data != "none":
        builder.row(InlineKeyboardButton(text="🔙 Назад к списку", callback_data=back_data))

    return builder.as_markup()
