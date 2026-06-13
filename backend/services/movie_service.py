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
    Получает список рекомендаций для конкретного фильма/сериала.
    """
    try:
        data = await tmdb.get_recommendations(movie_id, media_type)
        return data.get("results", []) if data else []
    except Exception as e:
        logger.error(f"Ошибка получения рекомендаций для {movie_id}: {e}")
        return []

async def ensure_movie_in_db(movie_id: int, media_type: str = "movie") -> bool:
    """Гарантирует, что тайтл есть в БД и он ПОЛНЫЙ (с актерами, временем и сезонами для сериалов)."""
    from config import db, tmdb
    import logging
    logger = logging.getLogger(__name__)

    movie_exists = await db.get_movie(movie_id)
    # Если тайтл есть И у него уже есть актеры — всё супер, качать не нужно
    if movie_exists and movie_exists.get("actors") and len(movie_exists["actors"]) > 0:
        return True
        
    try:   
        # 1. СРАЗУ качаем расширенную версию из TMDB
        if media_type == "tv":
            tmdb_ext = await tmdb.get_tv_details_extended(movie_id)
        else:
            tmdb_ext = await tmdb.get_movie_details_extended(movie_id)
            
        if not tmdb_ext:
            return False

        # 2. Вытаскиваем актеров, режиссеров и общие метаданные
        credits = tmdb_ext.get("credits", {})
        actors = [a.get("name") for a in credits.get("cast", [])[:5]]
        directors = [d.get("name") for d in credits.get("crew", []) if d.get("job") == "Director"]
        
        raw_poster = tmdb_ext.get("poster_path") or ""
        genres_array = [g.get("name") for g in tmdb_ext.get("genres", [])]

        # 3. Специфичная логика для фильмов и сериалов
        if media_type == "tv":
            runtime_mins = (tmdb_ext.get("episode_run_time", [0])[0] if tmdb_ext.get("episode_run_time") else 0)
            seasons = tmdb_ext.get("number_of_seasons", 0)
            tv_status = tmdb_ext.get("status", "") # TMDB отдает это в поле status
            
            release_date = tmdb_ext.get("first_air_date") or ""
            year = release_date[:4] if release_date else ""
            title = tmdb_ext.get("name") or "Без названия"
        else:
            runtime_mins = tmdb_ext.get("runtime", 0)
            seasons = 0
            tv_status = ""
            
            release_date = tmdb_ext.get("release_date") or ""
            year = release_date[:4] if release_date else ""
            title = tmdb_ext.get("title") or "Без названия"

        # 4. Формируем универсальный пакет данных
        movie_data = {
            "id": tmdb_ext.get("id", movie_id),
            "title": title,
            "year": year,
            "rating_numeric": tmdb_ext.get("vote_average", 0.0),
            "overview": tmdb_ext.get("overview", ""),
            "poster_url": raw_poster,
            "genres_array": genres_array,
            "media_type": media_type,
            "actors": actors,
            "directors": directors,
            "runtime_mins": runtime_mins,
            "seasons": seasons,
            "tv_status": tv_status  # ИСПОЛЬЗУЕМ ТВОЕ НАЗВАНИЕ КОЛОНКИ
        }
        
        await db.save_movie(movie_data)
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении {media_type} {movie_id} из TMDB: {e}")
        return False