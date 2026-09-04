from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

# Добавляем bot в импорт из config
from config import db, bot, recommendation_service
from services.media_state_service import apply_rating
from services.ui import render_and_send_card, send_list_menu 
# Импортируем наш новый сервис
from services.library_service import get_library_page_data
from keyboards.library_kb import library_menu_keyboard, library_list_keyboard
from utils.templates import (
    CB_BACK_TO_MENU_TEXT,
    CB_OPENING_LIST_TEXT,
)
from services.telegram_ui import parse_callback

router = Router()


@router.message(Command("library"))
@router.message(F.text.in_({"📚 Моё", "🔖 В планах", "🗄 Библиотека"}))
async def cmd_library(message: Message):
    if message.text == "🔖 В планах":
        await show_library_page(message.chat.id, "watchlist", 0)
    else:
        await send_list_menu(message.chat.id)

async def show_library_page(chat_id, status, page, edit_message=None, media_type="all"):
    page_size = 10
    actual_status = "liked" if status in {"top", "recent"} else status
    items, total = await get_library_page_data(chat_id, actual_status, page, page_size, None if media_type == "all" else media_type, "rating" if status == "top" else "updated_at")

    # Словарь для красивых заголовков
    status_titles = {
        "watchlist": "Хочу посмотреть",
        "liked": "Моё",
        "top": "Лучшие оценки",
        "recent": "Недавно добавленные",
        "archive": "Убрать"
    }

    if not items:
        text = f"В категории «{status_titles.get(status, status)}» пока пусто..." 
        markup = library_menu_keyboard()
    else:
        text = f"📂 <b>{status_titles.get(status, status)}</b> (всего: {total})"
        markup = library_list_keyboard(status, page, page_size, total, items, media_type)

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


@router.callback_query(F.data.startswith("lib:"))
async def cb_compact_library(callback: CallbackQuery) -> None:
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректный список", show_alert=True)
        return
    status, raw_page, media_type = action.args
    await callback.answer()
    await show_library_page(callback.message.chat.id, status, int(raw_page), callback.message, media_type)


@router.callback_query(F.data.startswith("libm:"))
async def cb_library_media(callback: CallbackQuery) -> None:
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Карточка устарела", show_alert=True)
        return
    item_media_type, raw_id, status, raw_page, media_type = action.args
    await callback.answer()
    await render_and_send_card(
        callback.message.chat.id,
        int(raw_id),
        callback.from_user.id,
        media_type=item_media_type,
        edit_message=callback.message,
        back_data=f"lib:{status}:{raw_page}:{media_type}",
    )

@router.callback_query(F.data == "main_menu_back")
async def cb_back_to_library_menu(callback: CallbackQuery) -> None:
    await callback.answer(CB_BACK_TO_MENU_TEXT)
    await send_list_menu(callback.message.chat.id, edit_message=callback.message)

@router.callback_query(F.data.startswith("rate_"))
async def cb_rate(callback: CallbackQuery) -> None:
    await callback.answer("Рейтинг обновлен!")
    parts = callback.data.split("_")
    if len(parts) == 4:
        _, media_type, raw_id, raw_rate = parts
    else:
        _, raw_id, raw_rate = parts
        media_type = "movie"
    if not raw_id.isdecimal() or not raw_rate.isdecimal() or int(raw_id) <= 0 or int(raw_rate) not in range(1, 6) or media_type not in {"movie", "tv"}:
        await callback.answer("Некорректная оценка", show_alert=True)
        return
    movie_id, rating = int(raw_id), int(raw_rate)
    
    # 1. Достаем данные из базы
    user_movie = await db.get_user_movie(callback.from_user.id, movie_id, media_type)
    if not user_movie and len(parts) == 3:
        # Legacy callbacks did not carry media_type; try TV only if movie is absent.
        user_movie = await db.get_user_movie(callback.from_user.id, movie_id, "tv")
    
    # 2. БРОНЕБОЙНАЯ ПРОВЕРКА (Исправляет твою ошибку)
    if user_movie:
        if isinstance(user_movie, dict):
            media_type = user_movie.get("media_type", "movie")
        else:
            media_type = getattr(user_movie, "media_type", "movie")

    await apply_rating(db, recommendation_service, callback.from_user.id, movie_id, media_type, rating)
    
    # 4. Передаем данные в Трубу, чтобы карточка перерисовалась с ✅
    await render_and_send_card(
        chat_id=callback.message.chat.id,
        movie_id=movie_id,
        user_id=callback.from_user.id,
        media_type=media_type,
        edit_message=callback.message
    )
