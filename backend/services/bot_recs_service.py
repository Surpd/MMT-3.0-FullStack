# services/bot_recs_service.py
import logging

logger = logging.getLogger(__name__)

async def get_bot_recommendations_batch(recs_service, user_id: int, batch_size: int = 5) -> list[dict]:
    """
    Запрашивает свежую пачку рекомендаций специально для Телеграм-бота, 
    игнорируя старый кэш Mini App.
    """
    try:
        # Дергаем ядро с принудительным обновлением!
        recommended_movies, _ = await recs_service.get_next_movies(
            user_id=user_id, 
            cursor=0, 
            force_refresh=True
        )
        
        if not recommended_movies:
            return []
            
        # Подстраховка для бота: старые хэндлеры ждут ключ 'id' вместо 'movie_id'
        for m in recommended_movies:
            if "id" not in m and "movie_id" in m:
                m["id"] = m["movie_id"]
                
        return recommended_movies[:batch_size]
        
    except Exception as e:
        logger.error(f"Ошибка при генерации пачки для бота: {e}")
        return []