from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.context import FSMContext
from config import bot
from services.search_service import get_search_results
from keyboards.search_kb import get_search_results_kb

router = Router()

# 1. Хэндлер кнопки "🔍 Поиск" (Точка входа в фильтры)
@router.message(F.text == "🔍 Поиск")
async def cmd_filter_search_menu(message: Message):
    """
    Здесь будет магия фильтров. 
    Пока что просто вежливо объясняем юзеру, что делать.
    """
    # В будущем здесь мы вызовем keyboards.filter_kb.get_filter_menu()
    await message.answer(
        "⚙️ **Расширенный поиск**\n\n"
        "Скоро здесь можно будет выбрать жанр, год и рейтинг.\n"
        "А пока — просто **напиши название фильма** в чат, и я его найду!"
    )

# 2. Обновленный основной хэндлер поиска
@router.message(F.text, ~F.text.startswith("/"))
async def handle_search_query(message: Message, state: FSMContext):
    query = (message.text or "").strip()
    
    # Теперь этот список исключений стал еще важнее
    if not query or query in ["🔍 Поиск", "🗄 Библиотека", "🎲 Что посмотреть?"]:
        return

    # Запускаем наш отлаженный механизм (из Шага 1 и 2)
    await state.update_data(current_query=query)

    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        results, source = await get_search_results(query, page=1)
        
        if not results:
            return await message.answer("Ничего не нашел. Проверь название? 🤔")

        kb = get_search_results_kb(results, page=1)
        await message.answer(f"<b>{source}</b> | Ищу: <i>{query}</i>", reply_markup=kb)

        
@router.callback_query(F.data.startswith("search_page_"))
async def handle_search_more(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Ещё варианты'."""
    # 1. Сразу убираем 'часики' на кнопке
    await callback.answer()
    
    # 2. Разбираем callback_data (search_more_название_страница)
    data = await state.get_data()
    query = data.get("current_query")
    page = int(callback.data.split("_")[-1])

    if not query:
        return await callback.message.answer("ÐŸÐ¾Ð¸ÑÐº Ð¿Ð¾Ñ‚ÐµÑ€ÑÐ½. ÐÐ°Ð¿Ð¸ÑˆÐ¸Ñ‚Ðµ Ð·Ð°Ð¿Ñ€Ð¾Ñ ÐµÑ‰Ñ‘ Ñ€Ð°Ð·.")

    # 3. Получаем данные через сервис (он сам проверит кэш или пойдет в TMDB)
    results, source = await get_search_results(query, page=page)
    
    if not results:
        return await callback.message.answer("Больше ничего не нашлось 🤷‍♂️")

    # 4. Генерируем новую клавиатуру (UI-слой)
    kb = get_search_results_kb(results, page=page)
    
    # 5. Редактируем текущее сообщение
    text = f"<b>{source}</b> | Результаты: <i>{query}</i> (Стр. {page})"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as e:
        # Иногда Телеграм ругается, если текст и кнопки абсолютно идентичны
        print(f"Ошибка обновления поиска: {e}")
