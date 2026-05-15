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

async def get_webapp_library_data(user_id: int, status: str = "liked", page: int = 1, limit: int = 50):
    """
    Готовит данные библиотеки специально для Mini App (Web App).
    Добавлены значения по умолчанию, чтобы api.py не падал.
    """
    offset = (page - 1) * limit
    
    # Идем на "Склад" за сырыми данными
    rows, total = await db.get_webapp_library(user_id, status, offset, limit)

    # "Готовим блюдо" для Web App
    image_base_url = "https://image.tmdb.org/t/p/w500"
    formatted_movies = []
    for row in rows:
        movies_data = row.get("movies") or {}
        poster_value = movies_data.get("poster_path") or movies_data.get("poster_url") or ""
        poster_path = poster_value if poster_value.startswith("http") else f"{image_base_url}{poster_value}" if poster_value else ""
        formatted_movies.append({
            "movie_id": row.get("movie_id"),
            "title": movies_data.get("title", "Без названия"),
            "poster_path": poster_path,
            "media_type": row.get("media_type", "movie"),
            "user_rating": row.get("rating")
        })

    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    return formatted_movies, total, total_pages
