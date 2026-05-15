from aiogram import Router, F
from aiogram.types import Message, CallbackQuery # Добавь CallbackQuery сюда!
from services.quiz_service import get_random_movie_id, build_quiz
from keyboards.quiz_kb import get_quiz_keyboard
from handlers.search import router as search_router
from config import db
from services.stats_service import stats_service
router = Router()# Подключаем твой новый файл с кнопками



@router.message(F.text == "🧠 Квиз")
async def start_quiz(message: Message):
    # 1. Отправляем предварительный статус
    status_msg = await message.answer("🔍 Ищу интересный фильм в базе...")

    try:
        # МАГИЯ ЗДЕСЬ: получаем реально случайный ID из базы!
        movie_id = await get_random_movie_id()
        
        # Вызываем нашу умную функцию (Шеф-повара)
        quiz_data = await build_quiz(movie_id)
        
        # Собираем кнопки
        kb = get_quiz_keyboard(quiz_data["options"], quiz_data["correct"])
        
        # Отправляем сам вопрос
        await message.answer(
            f"🎬 **Угадай фильм по описанию:**\n\n{quiz_data['question']}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        
        # Удаляем сообщение о загрузке
        await status_msg.delete()

    except Exception as e:
        await message.answer("⚠️ Ой, что-то пошло не так при сборке вопроса...")
        print(f"Ошибка в квизе: {e}")



# Эти импорты (F, CallbackQuery) у тебя уже должны быть в начале файла handlers/quiz.py

from config import db
from services.stats_service import stats_service

@router.callback_query(F.data.startswith("quiz_right"))
async def quiz_correct_answer(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # МАГИЯ: Ищем правильный ответ прямо в тексте кнопок, пока мы их не удалили!
    correct_movie = "Неизвестный фильм"
    if callback.message.reply_markup:
        for row in callback.message.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("quiz_right"):
                    correct_movie = btn.text
                    break

    # 1. Начисляем очки
    current_stats = await db.get_user_stats(user_id)
    new_stats, result_msg = stats_service.process_quiz_answer(True, current_stats)
    await db.update_user_stats(user_id, new_stats)
    
    # 2. Показываем тихую всплывашку с очками
    await callback.answer(result_msg, show_alert=False)
    
    # 3. Обновляем текст: хвалим и называем фильм
    old_text = callback.message.text or "Вопрос квиза"
    await callback.message.edit_text(
        f"{old_text}\n\n✅ **Отлично! Ответ верный.**\nЭто действительно фильм «*{correct_movie}*».", 
        reply_markup=None,
        parse_mode="Markdown"
    )
    
    # 4. Сразу запускаем следующий вопрос!
    await start_quiz(callback.message)


@router.callback_query(F.data.startswith("quiz_wrong"))
async def quiz_wrong_answer(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # МАГИЯ: Снова подсматриваем правильный ответ в кнопках
    correct_movie = "Неизвестный фильм"
    if callback.message.reply_markup:
        for row in callback.message.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("quiz_right"):
                    correct_movie = btn.text
                    break
                    
    # 1. Отнимаем очки
    current_stats = await db.get_user_stats(user_id)
    new_stats, result_msg = stats_service.process_quiz_answer(False, current_stats)
    await db.update_user_stats(user_id, new_stats)
    
    # 2. Показываем тихую всплывашку с очками
    await callback.answer(result_msg, show_alert=False)
    
    # 3. Обновляем текст: говорим, что ошибка, и палим правильный ответ
    old_text = callback.message.text or "Вопрос квиза"
    await callback.message.edit_text(
        f"{old_text}\n\n❌ **Слушай, это было неверно.**\nНа самом деле правильный ответ: «*{correct_movie}*».", 
        reply_markup=None,
        parse_mode="Markdown"
    )
    
    # 4. Сразу запускаем следующий вопрос!
    await start_quiz(callback.message)