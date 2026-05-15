import random
from config import tmdb
import logging


logger = logging.getLogger(__name__)

async def get_random_movie_id() -> int:
    """
    Выбирает случайный популярный фильм, вышедший начиная с 2006 года.
    """
    # 1. Делаем проверочный запрос, чтобы узнать количество страниц
    initial_data = await tmdb.discover_with_filters(year_from=2006)
    
    # ВАЖНО: У TMDB есть жесткий лимит — он отдает максимум 500 страниц
    # Даже если total_pages = 1000, 501-ю страницу он не отдаст. 
    max_pages = min(initial_data.get("total_pages", 1), 500)
    
    # 2. Выбираем случайную страницу
    random_page = random.randint(1, max_pages)
    
    # 3. Делаем второй запрос за конкретной случайной страницей
    page_data = await tmdb.discover_with_filters(year_from=2006, page=random_page)
    results = page_data.get("results", [])
    
    # 4. Если всё хорошо, берем случайный фильм с этой страницы
    if results:
        random_movie = random.choice(results)
        return random_movie["id"]
    
    # 5. Сейфгард (если TMDB вдруг затупил, отдадим Интерстеллар)
    return 157336


async def build_quiz(movie_id: int, media_type: str = "movie") -> dict:
    """
    Собирает данные для квиза.
    Если описания нет — ищет другой фильм.
    """
    try:
        # 1. Получаем детали (сохраняем в details)
        if media_type == "tv":
            details = await tmdb.get_tv_details_extended(movie_id)
            correct_title = details.get("name") or details.get("title", "Неизвестно")
        else:
            details = await tmdb.get_movie_details_extended(movie_id)
            correct_title = details.get("title") or details.get("name", "Неизвестно")

        # Достаем описание
        question = details.get("overview")

        # --- ПРОВЕРКА НА ПУСТОТУ (Валидация) ---
        # Проверяем именно details, а не raw_tmdb
        if not question or len(question) < 20:
            logger.warning(f"Фильм {movie_id} без нормального описания. Ищу замену...")
            from services.quiz_service import get_random_movie_id
            new_id = await get_random_movie_id()
            return await build_quiz(new_id, media_type)
        # ---------------------------------------

    except Exception as e:
        logger.error(f"Ошибка при сборке квиза для {movie_id}: {e}")
        return None

    # Дальше используем details для жанров
    genres_data = details.get("genres", [])
    genre_ids = [g["id"] for g in genres_data] if isinstance(genres_data, list) else []

    # ... (весь остальной код с Планом А, Б и В остается таким же) ...
    # Главное, что теперь переменная называется details и random импортирован.
    
    # 2. ПЛАН А: Ищем прямые рекомендации
    recs = await tmdb.get_recommendations(movie_id, media_type)
    wrong_options = []
    if recs and isinstance(recs, dict) and "results" in recs:
        for item in recs["results"]:
            title = item.get("title") or item.get("name")
            if title and title != correct_title and title not in wrong_options:
                wrong_options.append(title)
            if len(wrong_options) == 3: break

    # 3. ПЛАН Б: По жанрам
    if len(wrong_options) < 3 and media_type == "movie" and genre_ids:
        genre_recs = await tmdb.discover_with_filters(with_genres=genre_ids, year_from=2006)
        genre_results = genre_recs.get("results", [])
        random.shuffle(genre_results)
        for item in genre_results:
            title = item.get("title") or item.get("name")
            if title and title != correct_title and title not in wrong_options:
                wrong_options.append(title)
            if len(wrong_options) == 3: break

    # 4. ПЛАН В: Заглушки
    fallbacks = ["Начало", "Интерстеллар", "Мстители", "Матрица", "Шрек"]
    while len(wrong_options) < 3:
        fallback = random.choice(fallbacks)
        if fallback != correct_title and fallback not in wrong_options:
            wrong_options.append(fallback)

    # 5. ФИНАЛ
    options = [correct_title] + wrong_options
    random.shuffle(options)

    return {
        "question": question,
        "correct": correct_title,
        "options": options
    }