from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from config import daily_cache, db, session_cache, tmdb
from keyboards.quiz_kb import get_quiz_keyboard
from services.quiz_service import QuizService

router = Router()


def _service() -> QuizService:
    return QuizService(db, tmdb, session_cache, daily_cache)


@router.message(F.text == "🧠 Квиз")
async def start_quiz(message: Message):
    session = await _service().create_session(message.from_user.id, mode="cinema")
    if not session or session.get("locked") or not session.get("questions"):
        await message.answer("Квиз сейчас недоступен. Попробуйте позже.")
        return
    question = session["questions"][0]
    await message.answer(
        f"Киноквиз · 1 / {session['total']}\n\n{question['question']}",
        reply_markup=get_quiz_keyboard(question["options"], session["session_id"], question["id"]),
    )


@router.callback_query(F.data.startswith("quiz:"))
async def answer_quiz(callback: CallbackQuery):
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный ответ", show_alert=True)
        return
    _, session_id, question_id, raw_index = parts
    try:
        option_index = int(raw_index)
    except ValueError:
        await callback.answer("Некорректный ответ", show_alert=True)
        return
    state = await session_cache.get(f"quiz_session_{callback.from_user.id}_{session_id}")
    questions = state.get("questions") if isinstance(state, dict) else None
    index = len(state.get("answers", [])) if isinstance(state, dict) else -1
    if not isinstance(questions, list) or index < 0 or index >= len(questions):
        await callback.answer("Сессия завершена", show_alert=True)
        return
    current = questions[index]
    options = current.get("options") or []
    if current.get("id") != question_id or option_index < 0 or option_index >= len(options):
        await callback.answer("Некорректный ответ", show_alert=True)
        return
    result = await _service().answer_session(callback.from_user.id, session_id, question_id, options[option_index])
    if not result:
        await callback.answer("Сессия завершена", show_alert=True)
        return
    await callback.answer(result["message"])
    if result["complete"]:
        summary = result["result"]
        await callback.message.edit_text(
            f"Киноквиз завершён\n\nРезультат: {summary['correct']} / {summary['total']}\n"
            f"Точность: {summary['accuracy']}%\nСчёт: {summary['score']}\nXP: +{summary['earned_xp']}",
            reply_markup=None,
        )
        return
    next_state = await session_cache.get(f"quiz_session_{callback.from_user.id}_{session_id}")
    next_index = result["next_index"]
    next_question = next_state["questions"][next_index]
    await callback.message.edit_text(
        f"Киноквиз · {next_index + 1} / {len(next_state['questions'])}\n\n{next_question['question']}",
        reply_markup=get_quiz_keyboard(next_question["options"], session_id, next_question["id"]),
    )
