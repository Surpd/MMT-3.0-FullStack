# handlers/recommendations.py
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from services.bot_recs_service import get_bot_recommendations_batch
from services.ui import render_and_send_card
from utils.states import RecsState
from config import recommendation_service

router = Router()

# 1. Нажатие на главную кнопку "🎲 Что посмотреть?"
@router.message(F.text == "🎲 Что посмотреть?")
async def cmd_recs_start(message: Message, state: FSMContext):
    wait_msg = await message.answer("🧠 Анализирую твои вкусы и генерирую свежую подборку...")
    
    # Генерируем 5 свежих фильмов (force_refresh=True внутри сервиса)
    movies = await get_bot_recommendations_batch(recommendation_service, message.from_user.id, batch_size=5)
    
    if not movies:
        await wait_msg.edit_text("🤷‍♂️ Не удалось подобрать фильмы. Попробуй позже или оцени больше фильмов в Mini App!")
        return

    # Сохраняем пачку в память FSM
    await state.update_data(recs_batch=movies, current_idx=0)
    await state.set_state(RecsState.viewing_recs)
    
    await wait_msg.delete()
    
    # Отправляем первый фильм
    first_movie = movies[0]
    await render_and_send_card(
        chat_id=message.chat.id,
        movie_id=first_movie["movie_id"],
        user_id=message.from_user.id,
        media_type=first_movie.get("media_type", "movie"),
        is_recs_mode=True,
        rec_index=0,
        rec_total=len(movies)
    )

# 2. Навигация: Кнопка "Далее" или "Назад"
@router.callback_query(RecsState.viewing_recs, F.data.startswith("rec_nav_"))
async def cb_recs_navigation(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    # Получаем данные из памяти
    data = await state.get_data()
    movies = data.get("recs_batch", [])
    new_idx = int(callback.data.split("_")[2])
    
    if not movies or new_idx < 0 or new_idx >= len(movies):
        return

    # Обновляем индекс в памяти
    await state.update_data(current_idx=new_idx)
    
    # Перерисовываем карточку (редактируем текущее сообщение)
    current_movie = movies[new_idx]
    await render_and_send_card(
        chat_id=callback.message.chat.id,
        movie_id=current_movie["movie_id"],
        user_id=callback.from_user.id,
        media_type=current_movie.get("media_type", "movie"),
        is_recs_mode=True,
        rec_index=new_idx,
        rec_total=len(movies),
        edit_message=callback.message # Важно: редактируем, а не шлем новую
    )

# 3. Кнопка "Сгенерировать еще" в конце пачки
@router.callback_query(RecsState.viewing_recs, F.data == "rec_generate_new")
async def cb_recs_refresh(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Генерирую новую пачку...")
    # Просто вызываем ту же логику старта
    await cmd_recs_start(callback.message, state)