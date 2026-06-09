from aiogram import F, Router
from aiogram.types import CallbackQuery
from config import db
from services.ui import render_and_send_card, _send_recommendations_if_any
from services.movie_service import get_movie_data_package
from services.cards import CardFormatter
from services.movie_service import get_movie_recommendations
from keyboards.nav_kb import recommendations_keyboard
from utils.templates import RECOMMENDATIONS_HEADER_TEXT

# Создаем свой роутер для этого файла
router = Router()

# 1. Изменение статуса (Хочу, Видел, Архив)
@router.callback_query(F.data.startswith("status_"))
async def cb_status(callback: CallbackQuery):
    # Разбираем на 4 части, так как теперь передаем media_type
    _, status, movie_id, media_type = callback.data.split("_")
    
    # Сохраняем в базу (теперь с типом медиа!)
    await db.upsert_user_movie(callback.from_user.id, int(movie_id), status, media_type=media_type)
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
