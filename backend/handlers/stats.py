import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

# Проверь пути к своим сервисам
from config import db 
from services.stats_service import stats_service
from services.taste_service import get_taste_summary
from services.series_tracking_service import get_tracked_series_page, render_tracked_series_page
from keyboards.profile_kb import profile_keyboard, tracked_series_keyboard
from services.telegram_ui import parse_callback

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


async def _profile_text(user_id: int) -> str:
    try:
        watched = await db.get_user_media_by_status(user_id, "liked")
        watchlist = await db.get_user_media_by_status(user_id, "watchlist")
        taste = await get_taste_summary(user_id)
    except Exception:
        raise RuntimeError("profile_unavailable")
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
    return text[:4000]


@router.message(Command("profile"))
@router.message(F.text == "📊 Профиль")
async def show_profile_handler(message: Message):
    try:
        text = await _profile_text(message.from_user.id)
    except Exception:
        await message.answer("Не удалось загрузить профиль. Попробуйте ещё раз.")
        return
    await message.answer(text, reply_markup=profile_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("tracked:"))
async def show_tracked_series_handler(callback: CallbackQuery):
    action = parse_callback(callback.data)
    if not action:
        await callback.answer("Экран устарел", show_alert=True)
        return
    await callback.answer()
    page = int(action.args[0])
    try:
        items, total = await get_tracked_series_page(db, callback.from_user.id, page)
        text = render_tracked_series_page(items, page, total)
        markup = tracked_series_keyboard(items, page, total)
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await callback.answer("Не удалось загрузить отслеживаемые сериалы", show_alert=True)


@router.callback_query(F.data == "profile:menu")
async def back_to_profile_handler(callback: CallbackQuery):
    await callback.answer()
    try:
        text = await _profile_text(callback.from_user.id)
        await callback.message.edit_text(text, reply_markup=profile_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.answer("Не удалось загрузить профиль", show_alert=True)
