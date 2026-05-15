# keyboards/recs_kb.py
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def recs_card_keyboard(movie_id, user_status, media_type="movie", user_rating=None, current_index=0, total_count=5):
    builder = InlineKeyboardBuilder()

    # 1. Кнопка Детали всегда сверху
    # Мы передаем back_data="recs", чтобы бот знал, куда возвращаться
    builder.button(text="ℹ️ Детали", callback_data=f"expand_{media_type}_{movie_id}_recs")
    
    # 2. Кнопки оценки (Упрощенные для быстрой работы)
    if user_status == "none":
        builder.button(text="⏳ Хочу", callback_data=f"status_watchlist_{movie_id}_{media_type}")
        builder.button(text="✅ Видел", callback_data=f"status_liked_{movie_id}_{media_type}")
        builder.button(text="🗑 Архив", callback_data=f"status_archive_{movie_id}_{media_type}")
        builder.adjust(1, 3) # 1 ряд: Детали, 2 ряд: 3 кнопки статуса
    
    elif user_status == "liked":
        # Звезды
        for i in range(1, 6):
            text = f"✅ {i}" if user_rating == i else f"⭐ {i}"
            builder.button(text=text, callback_data=f"rate_{movie_id}_{i}")
        builder.button(text="🗑 В архив", callback_data=f"status_archive_{movie_id}_{media_type}")
        builder.adjust(1, 5, 1) # Детали -> Звезды -> Архив
        
    else:
        # Для watchlist или archive
        builder.button(text="✅ Видел", callback_data=f"status_liked_{movie_id}_{media_type}")
        builder.button(text="🔄 Убрать", callback_data=f"status_none_{movie_id}_{media_type}")
        builder.adjust(1, 2)

    # 3. НАВИГАЦИЯ ПО ПАЧКЕ (Та самая магия)
    nav_row = []
    
    if current_index > 0:
        # Если это не первый фильм, добавляем кнопку "Назад"
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"rec_nav_{current_index - 1}"))
    
    if current_index < total_count - 1:
        # Если есть еще фильмы впереди
        nav_row.append(InlineKeyboardButton(text=f"Далее ➡️ ({current_index + 1}/{total_count})", callback_data=f"rec_nav_{current_index + 1}"))
    else:
        # Если дошли до конца пачки
        nav_row.append(InlineKeyboardButton(text="🔄 Сгенерировать еще", callback_data="rec_generate_new"))
        
    builder.row(*nav_row)

    return builder.as_markup()