from config import tmdb, movie_cache, db
import logging

logger = logging.getLogger(__name__)

async def get_movie_data_package(movie_id: int, user_id: int, media_type: str = "movie"):
    """
    Собирает ПОЛНЫЙ пакет данных о фильме.
    Теперь использует только БД и строгую модель MovieModel, игнорируя сырой movie_cache.
    """
    from config import db
    from models.movie_model import MovieModel

    # 1. Данные пользователя (из БД)
    user_movie = await db.get_user_movie(user_id, movie_id)
    user_status = user_movie.status if user_movie else "none"
    user_rating = getattr(user_movie, 'rating', None) if user_movie else None

    # 2. Гарантируем, что полная версия фильма есть в БД (это и есть наш "умный кэш")
    await ensure_movie_in_db(movie_id, media_type)

    # 3. Читаем канонические данные из базы
    db_data = await db.get_movie(movie_id)
    if db_data:
        movie_obj = MovieModel.from_dict(db_data)
        # Превращаем в плоский словарь для совместимости с остальным кодом
        movie_dict = movie_obj.to_dict()
    else:
        movie_dict = {}

    # 4. Возвращаем готовый пакет 
    # (Ключ raw_tmdb оставлен умышленно, чтобы не сломать Telegram-бота, который его ждет)
    return {
        "raw_tmdb": movie_dict,
        "user_status": user_status,
        "user_rating": user_rating,
        "from_cache": True,
        "media_type": media_type
    }
    
async def get_movie_recommendations(movie_id: int, media_type: str = "movie"):
    """
    ÐŸÐ¾Ð»ÑƒÑ‡Ð°ÐµÑ‚ ÑÐ¿Ð¸ÑÐ¾Ðº Ñ€ÐµÐºÐ¾Ð¼ÐµÐ½Ð´Ð°Ñ†Ð¸Ð¹ Ð´Ð»Ñ ÐºÐ¾Ð½ÐºÑ€ÐµÑ‚Ð½Ð¾Ð³Ð¾ Ñ„Ð¸Ð»ÑŒÐ¼Ð°/ÑÐµÑ€Ð¸Ð°Ð»Ð°.
    """
    try:
        # Ð—Ð´ÐµÑÑŒ Ð¼Ñ‹ Ð² Ð±ÑƒÐ´ÑƒÑ‰ÐµÐ¼ Ð¼Ð¾Ð¶ÐµÐ¼ Ð¿Ñ€Ð¸ÐºÑ€ÑƒÑ‚Ð¸Ñ‚ÑŒ ÐºÑÑˆ, ÐµÑÐ»Ð¸ Ð·Ð°Ñ…Ð¾Ñ‚Ð¸Ð¼
        return await tmdb.get_recommendations(movie_id, media_type)
    except Exception as e:
        logger.error(f"ÐžÑˆÐ¸Ð±ÐºÐ° Ð¿Ð¾Ð»ÑƒÑ‡ÐµÐ½Ð¸Ñ Ñ€ÐµÐºÐ¾Ð¼ÐµÐ½Ð´Ð°Ñ†Ð¸Ð¹ Ð´Ð»Ñ {movie_id}: {e}")
        return []

async def ensure_movie_in_db(movie_id: int, media_type: str = "movie") -> bool:
    """Гарантирует, что фильм есть в БД и он ПОЛНЫЙ (с актерами и временем)."""
    from config import db, tmdb
    import logging
    logger = logging.getLogger(__name__)

    movie_exists = await db.get_movie(movie_id)
    # Если фильм есть И у него уже есть актеры — всё супер, ничего качать не нужно
    if movie_exists and movie_exists.get("actors") and len(movie_exists["actors"]) > 0:
        return True
        
    try:   
        # 1. СРАЗУ качаем расширенную версию
        if media_type == "tv":
            tmdb_ext = await tmdb.get_tv_details_extended(movie_id)
        else:
            tmdb_ext = await tmdb.get_movie_details_extended(movie_id)
            
        if not tmdb_ext:
            return False

        # 2. Вытаскиваем актеров, режиссеров и время
        credits = tmdb_ext.get("credits", {})
        actors = [a.get("name") for a in credits.get("cast", [])[:5]]
        directors = [d.get("name") for d in credits.get("crew", []) if d.get("job") == "Director"]
        runtime_mins = tmdb_ext.get("runtime") or (tmdb_ext.get("episode_run_time", [0])[0] if tmdb_ext.get("episode_run_time") else 0)

        # 3. Базовые поля
        raw_poster = tmdb_ext.get("poster_path") or ""
        release_date = tmdb_ext.get("release_date") or tmdb_ext.get("first_air_date") or ""
        year = release_date[:4] if release_date else ""
        genres_array = [g.get("name") for g in tmdb_ext.get("genres", [])]

        movie_data = {
            "id": tmdb_ext.get("id", movie_id),
            "title": tmdb_ext.get("title") or tmdb_ext.get("name") or "Без названия",
            "year": year,
            "rating_numeric": tmdb_ext.get("vote_average", 0.0),
            "overview": tmdb_ext.get("overview", ""),
            "poster_url": raw_poster,
            "genres_array": genres_array,
            "media_type": media_type,
            "actors": actors,
            "directors": directors,
            "runtime_mins": runtime_mins
        }
        await db.save_movie(movie_data)
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении фильма {movie_id} из TMDB: {e}")
        return False