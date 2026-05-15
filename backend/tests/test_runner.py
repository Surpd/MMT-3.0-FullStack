import asyncio
import os
import logging
from dotenv import load_dotenv

# 1. Загружаем переменные окружения (.env)
load_dotenv()

# 2. Настраиваем логирование (чтобы видеть детали ошибок)
logging.basicConfig(level=logging.INFO)

# 3. Твои настроенные импорты сервисов
from services.tmdb import TMDBClient
from services.cache import MemoryCache
from services.database import SupabaseDatabase
from services.quiz_service import build_quiz  # Важно: логика квиза теперь здесь

# 4. Создаем экземпляры для тестов
# Используем те же ключи, что и в основном боте
tmdb = TMDBClient(api_key=os.getenv("TMDB_API_KEY"))
movie_cache = MemoryCache(ttl_sec=3600)
db = SupabaseDatabase(
    url=os.getenv("SUPABASE_URL"),
    key=os.getenv("SUPABASE_KEY")
)

# Дальше идут твои функции тестов (test_tmdb, test_cache и т.д.)
async def test_tmdb():
    print("\n=== TMDB TEST ===")
    movie_id = 157336  # Интерстеллар

    details = await tmdb.get_movie_details_extended(movie_id)
    if not details:
        print("❌ TMDB details не пришли")
        return

    print("✅ TMDB details OK:", details.get("title"))

    recs = await tmdb.get_recommendations(movie_id)
    if not recs:
        print("❌ TMDB recommendations пустые")
        return

    print(f"✅ TMDB recommendations OK: {len(recs)} шт")


# === ТЕСТ: CACHE ===
async def test_cache():
    print("\n=== CACHE TEST ===")
    key = "test_key"
    value = {"hello": "world"}

    await movie_cache.put(key, value)
    cached = await movie_cache.get(key)

    if cached == value:
        print("✅ Cache работает")
    else:
        print("❌ Cache сломан")


# === ТЕСТ: DATABASE ===
# === ТЕСТ: DATABASE ===
async def test_database():
    print("\n=== DATABASE TEST ===")
    user_id = 999999
    movie_id = 157336

    # 1. Регистрируем профиль (уже работает)
    await db.ensure_user(user_id)

    # 2. !!! ДОБАВЛЯЕМ ЭТУ СТРОЧКУ !!!
    # Сначала сохраняем сам фильм в таблицу movies
    await db.save_movie({
        "id": movie_id, 
        "title": "Interstellar", 
        "media_type": "movie"
    })

    # 3. И только теперь связываем юзера с этим фильмом
    await db.upsert_user_movie(
        user_id=user_id,
        movie_id=movie_id,
        status="liked",
        media_type="movie",
        rating=5
    )

    record = await db.get_user_movie(user_id, movie_id)

    if record:
        print(f"✅ DB запись: статус={record.status}, рейтинг={record.rating}")
    else:
        print("❌ DB не вернула запись")


# === ТЕСТ: QUIZ ===
async def test_quiz():
    print("\n=== QUIZ TEST ===")

    from handlers.quiz import build_quiz

    data = await build_quiz(157336)

    if not data:
        print("❌ Quiz ничего не вернул")
        return

    print("✅ Quiz вопрос:", data["question"][:50])
    print("✅ Quiz варианты:", data["options"])


# === ТЕСТ: ПОЛНЫЙ СЦЕНАРИЙ ===
async def test_full_flow():
    print("\n=== FULL FLOW TEST ===")

    movie_id = 157336
    user_id = 999999

    # 1. TMDB
    details = await tmdb.get_movie_details_extended(movie_id)

    # 2. CACHE
    await movie_cache.put("test_movie", details)

    # 3. DB
    await db.upsert_user_movie(user_id, movie_id, "liked", rating=4)

    # 4. READ DB
    record = await db.get_user_movie(user_id, movie_id)

    print("🎬", details.get("title"))
    print("⭐", record.rating if record else "нет рейтинга")

    print("✅ FULL FLOW OK")

# === ЗАПУСК ===
async def main():
    await test_tmdb()
    await test_cache()
    await test_database()
    await test_quiz()
    await test_full_flow()


if __name__ == "__main__":
    asyncio.run(main())