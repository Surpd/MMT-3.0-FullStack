import asyncio
from config import db  # Твой новый красивый импорт
import os

async def run_test():
    test_id = 55555555
    movie_id = 550  # Бойцовский клуб
    
    print(f"🛠 1. Регистрируем юзера {test_id}...")
    await db.ensure_user(test_id, "test_hacker", "Ivan")
    
    print(f"🎬 2. Добавляем фильм {movie_id} в общий каталог...")
    # Используем твой объект db, чтобы сначала создать фильм
    # Это нужно, чтобы не вылетала ошибка Foreign Key по movie_id
    db._crud._client.table("movies").upsert({
        "id": movie_id, 
        "title": "Fight Club",
        "media_type": "movie"
    }).execute()
    
    print(f"🔗 3. Привязываем фильм к юзеру...")
    # Теперь и юзер, и фильм есть в базе — связь обязана сработать
    await db.upsert_user_movie(test_id, movie_id, "watched", media_type="movie")
    
    print("✅ ВСЁ! Тест прошел. База принимает данные и держит связи.")

if __name__ == "__main__":
    asyncio.run(run_test())