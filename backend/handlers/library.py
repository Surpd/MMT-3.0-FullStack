from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

# Добавляем bot в импорт из config
from config import db, bot 
from services.ui import render_and_send_card, send_list_menu 
# Импортируем наш новый сервис
from services.library_service import get_library_page_data
from keyboards.library_kb import library_menu_keyboard, library_list_keyboard
from utils.templates import (
    CB_BACK_TO_MENU_TEXT,
    CB_OPENING_LIST_TEXT,
)

router = Router()


@router.message(F.text == "🗄 Библиотека")
async def cmd_library(message: Message):
    await send_list_menu(message.chat.id)

async def show_library_page(chat_id, status, page, edit_message=None):
    page_size = 10
    items, total = await get_library_page_data(chat_id, status, page, page_size)

    # Словарь для красивых заголовков
    status_titles = {
        "watchlist": "⏳ Хочу посмотреть",
        "liked": "✅ Просмотрено",
        "archive": "🗑 Архив"
    }

    if not items:
        text = f"В категории «{status_titles.get(status, status)}» пока пусто..." 
        markup = library_menu_keyboard()
    else:
        text = f"📂 <b>{status_titles.get(status, status)}</b> (всего: {total})"
        markup = library_list_keyboard(status, page, page_size, total, items)

    if edit_message:
        try:
            await edit_message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode="HTML")
    else:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data.startswith("showlist_"))
async def cb_show_list(callback: CallbackQuery) -> None:
    await callback.answer(CB_OPENING_LIST_TEXT)
    _, status, raw_page = callback.data.split("_")
    await show_library_page(callback.message.chat.id, status, int(raw_page), callback.message)

@router.callback_query(F.data == "main_menu_back")
async def cb_back_to_library_menu(callback: CallbackQuery) -> None:
    await callback.answer(CB_BACK_TO_MENU_TEXT)
    await send_list_menu(callback.message.chat.id, edit_message=callback.message)

@router.callback_query(F.data.startswith("rate_"))
async def cb_rate(callback: CallbackQuery) -> None:
    await callback.answer("Рейтинг обновлен!")
    _, raw_id, raw_rate = callback.data.split("_")
    movie_id, rating = int(raw_id), int(raw_rate)
    
    # 1. Достаем данные из базы
    user_movie = await db.get_user_movie(callback.from_user.id, movie_id)
    
    # 2. БРОНЕБОЙНАЯ ПРОВЕРКА (Исправляет твою ошибку)
    media_type = "movie"
    if user_movie:
        if isinstance(user_movie, dict):
            media_type = user_movie.get("media_type", "movie")
        else:
            media_type = getattr(user_movie, "media_type", "movie")

    # 3. Сохраняем статус и оценку в Supabase
    await db.upsert_user_movie(
        user_id=callback.from_user.id, 
        movie_id=movie_id, 
        status="liked",
        media_type=media_type,
        rating=rating
    )
    
    # 4. Передаем данные в Трубу, чтобы карточка перерисовалась с ✅
    await render_and_send_card(
        chat_id=callback.message.chat.id,
        movie_id=movie_id,
        user_id=callback.from_user.id,
        media_type=media_type,
        edit_message=callback.message
    )