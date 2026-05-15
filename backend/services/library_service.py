from config import db

async def get_library_page_data(user_id: int, status: str, page: int, page_size: int = 10):
    """
    Запрашивает данные библиотеки.
    Убрали await, так как клиент работает в синхронном режиме.
    """
    start = page * page_size
    end = start + page_size - 1

    # УДАЛИЛИ await ТУТ
    rows, total = await db.get_library_page_rows(user_id=user_id, status=status, start=start, end=end)

    items = []
    for row in rows:
        # Проверяем наличие данных из связанной таблицы 'movies'
        title_data = row.get("movies")
        # Если фильма нет в общей таблице, пишем ID как заглушку
        movie_title = title_data.get("title") if title_data else f"ID: {row['movie_id']}"
        
        items.append((
            row["movie_id"],
            movie_title,
            row["media_type"],
            row.get("rating")
        ))

    return items, total

# services/library_service.py
from config import db

# ... твоя старая функция get_library_page_data ...

async def get_webapp_library_data(user_id: int, status: str, page: int, limit: int):
    """
    Готовит данные библиотеки специально для Mini App (Web App).
    """
    offset = (page - 1) * limit
    
    # Идем на "Склад" за сырыми данными
    rows, total = await db.get_webapp_library(user_id, status, offset, limit)

    # "Готовим блюдо" для Web App
    formatted_movies = []
    for row in rows:
        movies_data = row.get("movies") or {}
        formatted_movies.append({
            "movie_id": row.get("movie_id"),
            "title": movies_data.get("title", "Без названия"),
            "poster_path": movies_data.get("poster_url", ""),
            "media_type": row.get("media_type", "movie"),
            "user_rating": row.get("rating")
        })

    # Считаем страницы
    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    return formatted_movies, total, total_pages