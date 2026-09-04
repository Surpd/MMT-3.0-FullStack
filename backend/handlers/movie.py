from aiogram import F, Router
from aiogram.types import CallbackQuery
from config import db, recommendation_service
from services.media_state_service import apply_media_state
from services.ui import render_and_send_card, _send_recommendations_if_any
from services.movie_service import ensure_movie_in_db, get_movie_data_package
from services.cards import CardFormatter
from services.movie_service import get_movie_recommendations
from keyboards.nav_kb import recommendations_keyboard
from utils.templates import RECOMMENDATIONS_HEADER_TEXT
from services.telegram_ui import parse_callback
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

# Создаем свой роутер для этого файла
router = Router()


def _rating_keyboard(media_type: str, movie_id: int):
    kb = InlineKeyboardBuilder()
    for rating in range(1, 6):
        kb.button(text=f"{rating} ⭐", callback_data=f"rate:{media_type}:{movie_id}:{rating}")
    kb.adjust(5)
    return kb.as_markup()


@router.callback_query(F.data.startswith("a:"))
async def cb_compact_status(callback: CallbackQuery) -> None:
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректное действие", show_alert=True)
        return
    status, media_type, raw_id = action.args
    try:
        await apply_media_state(db, recommendation_service, callback.from_user.id, int(raw_id), media_type, status)
        await callback.answer("Готово")
        await render_and_send_card(callback.message.chat.id, int(raw_id), callback.from_user.id, media_type=media_type, edit_message=callback.message)
    except (ValueError, TypeError):
        await callback.answer("Не удалось изменить статус", show_alert=True)
    except Exception:
        await callback.answer("Не удалось изменить статус. Попробуйте ещё раз.", show_alert=True)


@router.callback_query(F.data.startswith("ratepick:"))
async def cb_rate_picker(callback: CallbackQuery) -> None:
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректное действие", show_alert=True)
        return
    media_type, raw_id = action.args
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=_rating_keyboard(media_type, int(raw_id)))


@router.callback_query(F.data.startswith("rate:"))
async def cb_compact_rating(callback: CallbackQuery) -> None:
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Некорректная оценка", show_alert=True)
        return
    media_type, raw_id, raw_rating = action.args
    try:
        # The card normally already populated the catalog. Refresh it when
        # needed, but do not turn a temporary TMDB outage into a rating failure.
        await ensure_movie_in_db(int(raw_id), media_type)
        await apply_rating(db, recommendation_service, callback.from_user.id, int(raw_id), media_type, int(raw_rating))
    except (ValueError, TypeError):
        await callback.answer("Оценка должна быть от 1 до 5", show_alert=True)
        return
    except Exception:
        await callback.answer("Не удалось сохранить оценку. Попробуйте ещё раз.", show_alert=True)
        return
    await callback.answer("Оценка сохранена ⭐")
    await render_and_send_card(callback.message.chat.id, int(raw_id), callback.from_user.id, media_type=media_type, edit_message=callback.message)


@router.callback_query(F.data.startswith("detail:"))
async def cb_compact_detail(callback: CallbackQuery) -> None:
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Карточка устарела", show_alert=True)
        return
    media_type, raw_id, *back = action.args
    await callback.answer()
    await render_and_send_card(callback.message.chat.id, int(raw_id), callback.from_user.id, media_type=media_type, is_full=True, edit_message=callback.message, back_data=back[0] if back else None)


@router.callback_query(F.data.startswith("m:"))
async def cb_compact_movie(callback: CallbackQuery) -> None:
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Карточка устарела", show_alert=True)
        return
    media_type, raw_id = action.args
    await callback.answer()
    await render_and_send_card(callback.message.chat.id, int(raw_id), callback.from_user.id, media_type=media_type, edit_message=callback.message)

# 1. Изменение статуса (Хочу, Видел, Архив)
@router.callback_query(F.data.startswith("status_"))
async def cb_status(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) == 3:
        _, status, movie_id = parts
        media_type = "movie"
    elif len(parts) == 4:
        _, status, movie_id, media_type = parts
    else:
        await callback.answer("Некорректное действие", show_alert=True)
        return
    if not movie_id.isdecimal() or int(movie_id) <= 0:
        await callback.answer("Некорректная карточка", show_alert=True)
        return
    if media_type not in {"movie", "tv"}:
        await callback.answer("Некорректный тип медиа", show_alert=True)
        return
    try:
        await apply_media_state(db, recommendation_service, callback.from_user.id, int(movie_id), media_type, status)
    except (ValueError, TypeError):
        await callback.answer("Некорректное действие", show_alert=True)
        return
    await callback.answer("Статус обновлен")
    
    # Перерисовываем карточку плавно
    await render_and_send_card(
        chat_id=callback.message.chat.id, 
        movie_id=int(movie_id), 
        user_id=callback.from_user.id, 
        media_type=media_type,
        edit_message=callback.message 
    )

# 2. Выбор фильма из списка (нажатие на название в Библиотеке)
@router.callback_query(F.data.startswith("movie_"))
async def cb_select(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    
    # movie_id и media_type всегда на 1 и 2 позициях
    movie_id, media_type = parts[1], parts[2]
    if not movie_id.isdecimal() or int(movie_id) <= 0 or media_type not in {"movie", "tv"}:
        await callback.answer("Некорректная карточка", show_alert=True)
        return
    print(f"DEBUG: Нажата карточка. ID: {movie_id}, Type: {media_type}")

    # Проверяем наличие хлебных крошек (status и page)[cite: 2]
    back_data = None
    if len(parts) >= 5:
        # Собираем путь для кнопки "Назад к списку"
        back_data = f"showlist_{parts[3]}_{parts[4]}"
    
    try:
        await render_and_send_card(
            chat_id=callback.message.chat.id, 
            movie_id=int(movie_id), 
            user_id=callback.from_user.id, 
            media_type=media_type,
            back_data=back_data, # Передаем память о странице[cite: 2]
            edit_message=callback.message # Заменяем список карточкой
        )
        print("DEBUG: Функция render_and_send_card отработала")
    except Exception as e:
        print(f"DEBUG: Ошибка в хэндлере cb_select: {e}")

# 3. Переключение режима "Детали" (Полное описание)
@router.callback_query(F.data.startswith("expand_"))
async def cb_expand_details(callback: CallbackQuery):
    await callback.answer()
    
    # Разбираем: expand_{media_type}_{movie_id}_{back_data}
    # Используем maxsplit=3, чтобы back_data (в которой есть _) не распилилась на части
    parts = callback.data.split("_", 3)
    
    # Проверяем, что данных хватает, чтобы бот не упал
    if len(parts) < 4:
        media_type, movie_id, back_data = parts[1], parts[2], "none"
    else:
        _, media_type, movie_id, back_data = parts
    
    await render_and_send_card(
        chat_id=callback.message.chat.id,
        movie_id=int(movie_id),
        user_id=callback.from_user.id,
        media_type=media_type,
        is_full=True, # Раз мы попали сюда, значит нажали на детали
        edit_message=callback.message,
        back_data=back_data if back_data != "none" else None
    )

# 4. Свернуть карточку (кратко)
@router.callback_query(F.data.startswith("collapse_"))
async def cb_collapse_details(callback: CallbackQuery):
    await callback.answer()

    # collapse_{media_type}_{movie_id}_{back_data}
    parts = callback.data.split("_", 3)
    if len(parts) < 4:
        media_type, movie_id, back_data = parts[1], parts[2], "none"
    else:
        _, media_type, movie_id, back_data = parts

    await render_and_send_card(
        chat_id=callback.message.chat.id,
        movie_id=int(movie_id),
        user_id=callback.from_user.id,
        media_type=media_type,
        is_full=False,
        edit_message=callback.message,
        back_data=back_data if back_data != "none" else None,
    )


# 5. 🔮 Похожие (отдельной кнопкой)
@router.callback_query(F.data.startswith("similar_"))
async def cb_similar(callback: CallbackQuery):
    await callback.answer("Ищу похожие...")
    _, media_type, movie_id = callback.data.split("_")
    
    # Запрашиваем напрямую у TMDB, так как чистая БД не хранит кэш рекомендаций
    from config import tmdb
    try:
        raw_recoms = await tmdb.get_recommendations(movie_id=int(movie_id), media_type=media_type)
        recoms = raw_recoms.get("results", []) if raw_recoms else []
        
        if not recoms:
            await callback.answer("К сожалению, похожих проектов не найдено 😔", show_alert=True)
            return
            
        # Имитируем пакет данных для отправки
        package = {"recommendations": recoms}
        await _send_recommendations_if_any(callback.message.chat.id, int(movie_id), media_type, package)
    except Exception as e:
        print(f"Ошибка в cb_similar: {e}")
        await callback.answer("Произошла ошибка при поиске 😔", show_alert=True)

# 6. Реролл рекомендаций (Тот самый, что я чуть не проспал!)
@router.callback_query(F.data.startswith("reroll_"))
async def cb_reroll(callback: CallbackQuery):
    await callback.answer("Ищу варианты...")
    print(f"DEBUG: Нажат реролл. Данные: {callback.data}")
    try:
        # Разбираем: reroll_{media_type}_{parent_movie_id}_{offset}[cite: 2]
        _, media_type, parent_movie_id, offset = callback.data.split("_")
        offset = int(offset)
        
        recoms = await get_movie_recommendations(int(parent_movie_id), media_type)
        print(f"DEBUG: Сервис вернул {len(recoms) if recoms else 0} рекомендаций")
        
        if not recoms or offset >= len(recoms):
            await callback.message.edit_text("🎯 Больше рекомендаций нет.")
            return

        try:
            items = [(r["id"], r["title"], media_type) for r in recoms[offset:offset + 3]]
        except (TypeError, KeyError):
            items = [(r.movie_id, r.title, media_type) for r in recoms[offset:offset + 3]]
            
        markup = recommendations_keyboard(items, int(parent_movie_id), offset, len(recoms) > offset + 3, media_type)
        await callback.message.edit_reply_markup(reply_markup=markup)
        print("DEBUG: Реролл успешно отработал!")
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА РЕРОЛЛА: {type(e).__name__} - {e}")
