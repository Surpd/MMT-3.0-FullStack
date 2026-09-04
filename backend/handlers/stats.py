import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

# Проверь пути к своим сервисам
from config import db 
from services.stats_service import stats_service
from services.taste_service import get_taste_summary

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


@router.message(Command("profile"))
@router.message(F.text == "📊 Профиль")
async def show_profile_handler(message: Message):
    user_id = message.from_user.id
    try:
        watched = await db.get_user_media_by_status(user_id, "liked")
        watchlist = await db.get_user_media_by_status(user_id, "watchlist")
        taste = await get_taste_summary(user_id)
    except Exception:
        await message.answer("Не удалось загрузить профиль. Попробуйте ещё раз.")
        return
    movies = sum((row.get("media_type") or "movie") == "movie" for row in watched)
    series = sum((row.get("media_type") or "movie") == "tv" for row in watched)
    ratings = [row.get("rating") for row in watched if isinstance(row.get("rating"), int)]
    average = f"{sum(ratings) / len(ratings):.1f}/5" if ratings else "н/д"
    genres = taste.get("genres") or []
    genre_text = ", ".join(html.escape(str(item.get("name"))) for item in genres[:5] if item.get("name")) or "пока нет данных"
    directors = ", ".join(html.escape(str(item.get("name"))) for item in (taste.get("directors") or [])[:5] if item.get("name")) or "пока нет данных"
    text = (
        "📊 <b>Профиль</b>\n\n"
        f"🎬 Просмотрено фильмов: {movies}\n📺 Просмотрено сериалов: {series}\n"
        f"⭐ Средняя оценка: {average}\n🔖 В планах: {len(watchlist)}\n\n"
        f"❤️ Любимые жанры\n<i>Доля просмотренной коллекции с этим жанром:</i> {genre_text}\n\n"
        f"🎬 Любимые режиссёры: {directors}"
    )
    await message.answer(text[:4000], parse_mode="HTML")
