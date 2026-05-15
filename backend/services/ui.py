import logging
from aiogram.types import Message, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest
from keyboards.recs_kb import recs_card_keyboard

# Оставили только BOT, так как мы через него шлем сообщения
from config import bot 

# Сюда ушла вся логика TMDB, Кэша и (в идеале) Базы
from services.movie_service import get_movie_data_package

from services.cards import CardFormatter
from keyboards.movie_kb import movie_card_keyboard
from keyboards.library_kb import library_menu_keyboard
# ВНИМАНИЕ: Если ты уже перенес library_menu_keyboard в library_kb, поправь импорт ниже
from keyboards.nav_kb import  recommendations_keyboard
from utils.templates import LIBRARY_MENU_TEXT, RECOMMENDATIONS_HEADER_TEXT, EMPTY_WISH_TEXT

logger = logging.getLogger(__name__)
DEFAULT_POSTER_URL = "https://dummyimage.com/600x900/9ca3af/ffffff&text=No+Poster"

async def render_and_send_card(chat_id, movie_id, user_id, media_type="movie", is_full=False, edit_message=None, back_data=None, is_recs_mode=False, rec_index=0, rec_total=5):
    try:
        # 1. ПОЛУЧЕНИЕ ДАННЫХ
        data = await get_movie_data_package(movie_id, user_id, media_type)
        package = CardFormatter.get_card_package(
            data["raw_tmdb"], 
            media_type, 
            data["user_status"], 
            is_full=is_full,
            recommendations=data["raw_tmdb"].get("recoms_cache")
        )

        # 2. ОПРЕДЕЛЯЕМ КОНТЕКСТ (Поиск или Библиотека)
        # Если back_data нет или там есть 'search' — это поиск
        
        # Меняем текст кнопки деталей, если мы в библиотеке и еще не открыли их
        # 3. ГЕНЕРАЦИЯ КЛАВИАТУРЫ
        # Передаем наш динамический текст кнопки (из Шага 1)
        # 3. ГЕНЕРАЦИЯ КЛАВИАТУРЫ
        if is_recs_mode:
            markup = recs_card_keyboard(
                movie_id=movie_id,
                user_status=data["user_status"],
                media_type=media_type,
                user_rating=data["user_rating"],
                current_index=rec_index,
                total_count=rec_total
            )
        else:
            markup = movie_card_keyboard(
                movie_id, 
                data["user_status"], 
                media_type, 
                data["user_rating"], 
                back_data=back_data,
                is_full=is_full
            )

        # 4. ЛОГИКА ОТПРАВКИ И РЕКОМЕНДАЦИЙ
        is_text_message = edit_message and not edit_message.photo
        poster_url = package.get("poster") or DEFAULT_POSTER_URL

        if edit_message and not is_text_message:
            # РЕДАКТИРОВАНИЕ (Теперь с обновлением фото!)
            try:
                # Создаем объект "Медиа", который содержит новое фото и новый текст
                media = InputMediaPhoto(
                    media=poster_url,
                    caption=package["caption"],
                    parse_mode="HTML"
                )
                
                await edit_message.edit_media(
                    media=media,
                    reply_markup=markup
                )
            except Exception as e:
                # Если вдруг фото не сменилось (например, URL тот же), просто обновим кнопки
                logger.warning(f"Не удалось обновить медиа: {e}")
                await edit_message.edit_reply_markup(reply_markup=markup)
        
        else:
            # НОВАЯ КАРТОЧКА (Отправка первого сообщения)
            await bot.send_photo(
                chat_id=chat_id, 
                photo=poster_url, 
                caption=package["caption"], 
                reply_markup=markup, 
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Ошибка при отрисовке карточки фильма {movie_id}: {e}")
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ЧИСТОТЫ КОДА
async def _send_recommendations_if_any(chat_id, movie_id, media_type, package):
    recoms = package.get("recommendations", [])
    if recoms:
        try:
            # Пробуем достать данные (зависит от того, пришел список или объекты)
            items = [(r["id"], r["title"], media_type) for r in recoms[:3]]
        except (KeyError, TypeError):
            items = [(r.movie_id, r.title, media_type) for r in recoms[:3]]
            
        rec_markup = recommendations_keyboard(items, movie_id, 0, len(recoms) > 3, media_type)
        await bot.send_message(chat_id, RECOMMENDATIONS_HEADER_TEXT, reply_markup=rec_markup)
        
async def send_list_menu(chat_id: int, edit_message: Message | None = None) -> None:
    """Отправляет главное меню библиотеки."""
    # Не забудь проверить импорт library_menu_keyboard в начале файла!
    markup = library_menu_keyboard()

    # Если мы пытаемся отредактировать сообщение с ФОТО (карточку) в ТЕКСТ (меню) — это не выйдет
    if edit_message and not edit_message.photo:
        try:
            await edit_message.edit_text(LIBRARY_MENU_TEXT, reply_markup=markup)
            return
        except Exception:
            pass
    
    # Если это была карточка с фото или новый вызов — просто шлем новое сообщение с меню
    await bot.send_message(chat_id=chat_id, text=LIBRARY_MENU_TEXT, reply_markup=markup)
