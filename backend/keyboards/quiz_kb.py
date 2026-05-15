from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Router, F

def get_quiz_keyboard(options: list, correct: str):
    """
    Собирает клавиатуру для квиза.
    options - список всех вариантов ответа.
    correct - правильный вариант.
    """
    builder = InlineKeyboardBuilder()
    
    for option in options:
        # Прячем правильный/неправильный ответ в callback_data
        cb_data = "quiz_right" if option == correct else "quiz_wrong"
        
        builder.button(
            text=option,
            callback_data=cb_data
        )
        
    # Располагаем кнопки столбиком (по 1 в ряд)
    builder.adjust(1)
    
    return builder.as_markup()
