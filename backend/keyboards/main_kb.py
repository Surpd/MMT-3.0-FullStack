from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Рекомендации"), KeyboardButton(text="🔎 Найти")],
            [KeyboardButton(text="📚 Моё"), KeyboardButton(text="🔖 В планах")],
            [KeyboardButton(text="📊 Профиль"), KeyboardButton(text="🧠 Квиз")],
            [KeyboardButton(text="🌐 Открыть приложение")],
        ],
        resize_keyboard=True,
    )
