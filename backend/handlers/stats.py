from aiogram import F, Router
from aiogram.types import Message

# Проверь пути к своим сервисам
from config import db 
from services.stats_service import stats_service

# Создаем локальный роутер для этого файла
router = Router() 

@router.message(F.text == "📊 Статистика")
async def show_statistics_handler(message: Message):
    user_id = message.from_user.id
    
    user_data = await db.get_user_stats(user_id)
    
    if not user_data:
        await message.answer("Статистика пока пуста. Напиши /start, чтобы зарегистрироваться!")
        return

    points = user_data.get("points", 0)
    quiz_total = user_data.get("quiz_total", 0)
    quiz_correct = user_data.get("quiz_correct", 0)
    current_streak = user_data.get("current_streak", 0)
    best_streak = user_data.get("best_streak", 0)

    level, title = stats_service.get_level_info(points)

    winrate = int((quiz_correct / quiz_total) * 100) if quiz_total > 0 else 0

    text = (
        f"👤 <b>Твой профиль:</b>\n"
        f"🏅 Звание: <b>{title}</b> ({level} уровень)\n"
        f"✨ Опыт: {points} XP\n\n"
        f"🎯 <b>Квизы:</b>\n"
        f"Ответов: {quiz_total} (Верных: {quiz_correct})\n"
        f"Точность: {winrate}%\n\n"
        f"🔥 Текущий стрик: {current_streak}\n"
        f"🏆 Рекордный стрик: {best_streak}"
    )

    await message.answer(text, parse_mode="HTML")