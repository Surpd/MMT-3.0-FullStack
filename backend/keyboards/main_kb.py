from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Что посмотреть?"), KeyboardButton(text="🧠 Квиз")],
            [KeyboardButton(text="🔍 Поиск"), KeyboardButton(text="🗄 Библиотека")],[KeyboardButton(text="📊 Статистика")]
        ],
        resize_keyboard=True,
    )
    return keyboard 
    