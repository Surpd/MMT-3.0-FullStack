from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Рекомендации"), KeyboardButton(text="🔎 Найти")],
            [KeyboardButton(text="📚 Моё"), KeyboardButton(text="🔖 В планах")],
            [KeyboardButton(text="📺 Сериалы"), KeyboardButton(text="📊 Профиль")],
            [KeyboardButton(text="🌐 Открыть приложение")],
            [KeyboardButton(text="🧠 Квиз")],
        ],
        resize_keyboard=True,
    )
