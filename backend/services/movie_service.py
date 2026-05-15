from config import tmdb, movie_cache, db
import logging

logger = logging.getLogger(__name__)

async def get_movie_data_package(movie_id: int, user_id: int, media_type: str = "movie"):
    """
    Собирает ПОЛНЫЙ пакет данных о фильме: из кэша, TMDB и твоей базы.
    Умеет работать и со словарями, и с объектами.
    """
    # 1. Данные пользователя (из твоей БД)
    user_movie = await db.get_user_movie(user_id, movie_id)
    user_status = user_movie.status if user_movie else "none"
    user_rating = getattr(user_movie, 'rating', None) if user_movie else None

    # 2. Глобальные данные (Кэш + TMDB)
    cache_key = f"tmdb_raw_{media_type}_{movie_id}"
    raw_tmdb = await movie_cache.get(cache_key)
    from_cache = True
    
    # Если в кэше пусто, идем в TMDB
    if not raw_tmdb:
        from_cache = False
        try:
            if media_type == "tv":
                raw_tmdb = await tmdb.get_tv_details_extended(movie_id)
            else:
                raw_tmdb = await tmdb.get_movie_details_extended(movie_id)
            
            if raw_tmdb:
                # Подтягиваем рекомендации для кэша
                recoms_list = await tmdb.get_recommendations(movie_id, media_type)
                
                # УНИВЕРСАЛЬНАЯ ЗАПИСЬ: проверяем тип
                if isinstance(raw_tmdb, dict):
                    raw_tmdb["recoms_cache"] = recoms_list
                else:
                    setattr(raw_tmdb, "recoms_cache", recoms_list)
                
                # Кладем в кэш
                await movie_cache.put(cache_key, raw_tmdb)
                
        except Exception as e:
            logger.error(f"Ошибка при запросе к TMDB: {e}")
            return None

    # 3. Сохранение фильма в НАШУ базу (чиним ошибку Foreign Key)
    if raw_tmdb:
        try:
            # УНИВЕРСАЛЬНОЕ ЧТЕНИЕ: проверяем тип
            if isinstance(raw_tmdb, dict):
                movie_title = raw_tmdb.get("title") or raw_tmdb.get("name", "Без названия")
                tmdb_id = raw_tmdb.get("id", movie_id)
            else:
                movie_title = getattr(raw_tmdb, "title", getattr(raw_tmdb, "name", "Без названия"))
                tmdb_id = getattr(raw_tmdb, "id", movie_id)
            
            movie_data = {
                "id": tmdb_id,
                "title": movie_title,
                "media_type": media_type
            }
            # Сохраняем/обновляем фильм в БД
            await db.save_movie(movie_data) 
        except Exception as e:
            logger.error(f"Не удалось сохранить фильм {movie_id} в БД: {e}")

    # 4. Возвращаем готовый пакет
    return {
        "raw_tmdb": raw_tmdb,
        "user_status": user_status,
        "user_rating": user_rating,
        "from_cache": from_cache,
        "media_type": media_type
    }

async def get_movie_recommendations(movie_id: int, media_type: str = "movie"):
    """
    Получает список рекомендаций для конкретного фильма/сериала.
    """
    try:
        # Здесь мы в будущем можем прикрутить кэш, если захотим
        return await tmdb.get_recommendations(movie_id, media_type)
    except Exception as e:
        logger.error(f"Ошибка получения рекомендаций для {movie_id}: {e}")
        return []