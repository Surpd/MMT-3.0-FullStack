from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_quiz_keyboard(options: list[str], session_id: str, question_id: str):
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        builder.button(text=option, callback_data=f"quiz:{session_id}:{question_id}:{index}")
    builder.adjust(1)
    return builder.as_markup()
