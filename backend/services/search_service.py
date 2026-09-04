import re
import json
import asyncio
import logging
import aiohttp
from config import tmdb, search_cache, GROQ_API_KEY
from utils.genres import TMDB_GENRES


GENRE_MAP = {
    "боевик": 28, "приключен": 12, "мульт": 16, "комед": 35, "криминал": 80,
    "документал": 99, "драм": 18, "семейн": 10751, "фэнтез": 14, "истор": 36,
    "ужас": 27, "музык": 10402, "детектив": 9648, "мелодрам": 10749,
    "фантастик": 878, "триллер": 53, "военн": 10752, "вестерн": 37
}
GROQ_MODEL = "openai/gpt-oss-120b"
AI_MEDIA_TYPES = {"movie", "tv"}


def _parse_ai_movies(content: str) -> list[dict]:
    try:
        start = content.find("{")
        if start < 0:
            return []
        payload, _ = json.JSONDecoder().raw_decode(content[start:])
        raw_movies = payload.get("movies", []) if isinstance(payload, dict) else []
    except (json.JSONDecodeError, TypeError, AttributeError):
        return []

    movies = []
    seen = set()
    for item in raw_movies:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        year = item.get("year")
        media_type = item.get("media_type")
        if not isinstance(title, str) or not title.strip():
            continue
        if media_type not in AI_MEDIA_TYPES:
            continue
        if isinstance(year, bool):
            continue
        try:
            year = int(year)
        except (TypeError, ValueError):
            continue
        if not 1888 <= year <= 2100:
            continue
        key = (title.strip().casefold(), year, media_type)
        if key in seen:
            continue
        seen.add(key)
        movies.append({"title": title.strip(), "year": year, "media_type": media_type})
        if len(movies) == 10:
            break
    return movies


def _pick_ai_match(items, ai_movie: dict):
    target_year = str(ai_movie.get("year", ""))
    target_title = str(ai_movie.get("title", "")).strip().casefold()
    target_media_type = ai_movie.get("media_type")

    def title_of(item):
        return (item.get("title") or item.get("name") if isinstance(item, dict) else getattr(item, "title", ""))

    def year_of(item):
        if isinstance(item, dict):
            release_date = item.get("release_date") or item.get("first_air_date") or ""
            return str(release_date)[:4]
        return str(getattr(item, "year", ""))[:4]

    def media_type_of(item):
        if isinstance(item, dict):
            return item.get("media_type")
        return getattr(item, "media_type", None)

    candidates = [
        item for item in items
        if year_of(item) == target_year and media_type_of(item) == target_media_type
    ]
    if not candidates:
        return None
    exact = [item for item in candidates if str(title_of(item)).strip().casefold() == target_title]
    return exact[0] if exact else candidates[0]

async def get_ai_movie_recommendations(query: str):
    if not GROQ_API_KEY:
        logging.warning("AI fallback unavailable: GROQ_API_KEY is not configured")
        return []
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    system_prompt = (
        "Ты киноман и эксперт. Твоя задача — найти до 10 фильмов, которые максимально точно подходят под описание пользователя. "
        "Отсортируй выдачу по порядку: на первые места ставь самые релевантные и известные совпадения и высокий рейтинг, а дальше — менее популярные, но идеально подходящие по смыслу. "
        "Обязательно используй точные официальные русские названия. Делай акцент на российского пользователя "
        "Верни строго JSON с ключом 'movies'. Это должен быть массив объектов с 'title' (название), 'year' (год выхода) и "
        "'media_type' (ровно 'movie' или 'tv'). Пример: {\"movies\": [{\"title\": \"Твоё имя\", \"year\": 2016, "
        "\"media_type\": \"movie\"}, {\"title\": \"Очень странные дела\", \"year\": 2016, \"media_type\": \"tv\"}]}. "
        "Никакого лишнего текста."
    )
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
        "temperature": 0.5
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    error_code = "unknown"
                    try:
                        error_data = await resp.json(content_type=None)
                        error_code = (error_data.get("error") or {}).get("code", error_code)
                    except (TypeError, ValueError, KeyError, AttributeError):
                        pass
                    logging.error(
                        "AI upstream error status=%s code=%s model=%s",
                        resp.status,
                        error_code,
                        GROQ_MODEL,
                    )
                    return []
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                movies = _parse_ai_movies(content)
                if not movies:
                    logging.error("AI response parse error model=%s", GROQ_MODEL)
                return movies
    except Exception:
        logging.exception("AI upstream error model=%s", GROQ_MODEL)
        return []

def parse_smart_query(query: str):
    query_lower = query.lower()
    found_genres = [genre_id for kw, genre_id in GENRE_MAP.items() if kw in query_lower]
    year_match = re.search(r'\b(19[5-9]\d|20[0-2]\d)\b', query_lower)
    return found_genres, int(year_match.group()) if year_match else None

async def get_search_results(query: str, page: int = 1, user_id: int = None):
    query_clean = query.strip()
    cache_key = f"hybrid_{query_clean}_{page}"
    
    cached = await search_cache.get(cache_key)
    if cached: return cached, "⚡ RAM"

    print(f"\n🔍 [DEBUG]: НАЧИНАЕМ ПОИСК: '{query_clean}'")

    # === ШАГ 0: Перехват системных тегов (ЭКОНОМИЯ ЛИМИТОВ ИИ) ===
    import random
    from config import recommendation_service
    
    q_lower = query_clean.lower()
    
    if q_lower == "топ рейтинг":
        print("⚡ [DEBUG ШАГ 0]: Перехватили 'Топ рейтинг'")
        
        user_genres = []
        if user_id:
            try:
                # Достаем вкусы юзера из базы
                _, top_genre_ids, _, _, _ = await recommendation_service._get_user_context(user_id)
                user_genres = top_genre_ids
            except Exception:
                pass
                
        # Базовый запрос: высокооцененные фильмы, берем случайную страницу из топ-5 для разнообразия
        kwargs = {
            "sort_by": "vote_average.desc", 
            "vote_count.gte": 2000, 
            "page": random.randint(1, 5) 
        }
        
        # В 75% случаев подмешиваем ОДИН из твоих любимых жанров.
        # Оставшиеся 25% дадут чистый мировой топ, чтобы расширять кругозор.
        if user_genres and random.random() < 0.75:
            kwargs["with_genres"] = [random.choice(user_genres)]
            
        try:
            res = await tmdb.discover_with_filters(**kwargs)
            items = res.get("results", []) if isinstance(res, dict) else res
            if items: 
                random.shuffle(items) # Шаффлим, чтобы не смотрелось как таблица Excel
                return items, "👑 Топ для тебя"
        except Exception: pass
        
    elif q_lower == "случайное кино":
        print("⚡ [DEBUG ШАГ 0]: Перехватили 'Случайное кино'")
        # Увеличили разброс страниц до 30 для максимального рандома
        kwargs = {"sort_by": "popularity.desc", "vote_count.gte": 500, "page": random.randint(1, 30)}
        try:
            res = await tmdb.discover_with_filters(**kwargs)
            items = res.get("results", []) if isinstance(res, dict) else res
            if items:
                random.shuffle(items)
                return items, "🎲 Рандом"
        except Exception: pass
            
    elif q_lower == "новинки 2026":
        print("⚡ [DEBUG ШАГ 0]: Перехватили 'Новинки 2026'")
        # Рандомим первые 3 страницы новинок
        kwargs = {"year_from": 2026, "year_to": 2026, "sort_by": "popularity.desc", "page": random.randint(1, 3)}
        try:
            res = await tmdb.discover_with_filters(**kwargs)
            items = res.get("results", []) if isinstance(res, dict) else res
            if items: 
                random.shuffle(items)
                return items, "🔥 Новинки"
        except Exception: pass

    # === ШАГ 1: Умные теги ===
    found_genres, year = parse_smart_query(query_clean)
    if found_genres or year:
        kwargs = {"page": page}
        
        # ИСПРАВЛЕНИЕ: Передаем именно список для твоей функции!
        if found_genres: 
            kwargs["with_genres"] = found_genres
            
        # ИСПРАВЛЕНИЕ: Используем родные параметры year_from и year_to!
        if year: 
            kwargs["year_from"] = year
            kwargs["year_to"] = year
        
        kwargs["sort_by"] = "vote_average.desc"
        kwargs["vote_count.gte"] = 300
        
        print(f"➡️ [DEBUG ШАГ 1]: Идем в discover с аргументами: {kwargs}")
        try:
            res_data = await tmdb.discover_with_filters(**kwargs)
            smart_results = res_data.get("results", []) if isinstance(res_data, dict) else (res_data if isinstance(res_data, list) else [])
            if smart_results:
                print(f"✅ [DEBUG ШАГ 1]: Нашли {len(smart_results)} фильмов по тегам.")
                await search_cache.put(cache_key, smart_results)
                return smart_results, "⚙️ Умный фильтр"
        except Exception as e:
            print(f"❌ [DEBUG ШАГ 1 ОШИБКА]: {e}")
    else:
        print(f"⏭️ [DEBUG ШАГ 1]: Нет тегов.")

    # === ШАГ 2: Обычный поиск ===
    print(f"➡️ [DEBUG ШАГ 2]: Обычный поиск в TMDB...")
    try:
        tmdb_res = await tmdb.search_movies(query_clean, page=page)
        tmdb_results = tmdb_res.get("results", []) if isinstance(tmdb_res, dict) else tmdb_res
        if tmdb_results and len(tmdb_results) > 0:
            print(f"✅ [DEBUG ШАГ 2]: Нашли {len(tmdb_results)} совпадений.")
            await search_cache.put(cache_key, tmdb_results)
            return tmdb_results, "🔍 TMDB"
    except Exception as e:
        print(f"❌ [DEBUG ШАГ 2 ОШИБКА]: {e}")

    # === ШАГ 3: Нейросеть (если есть ключ) ===
    if page == 1 and GROQ_API_KEY:
        print(f"➡️ [DEBUG ШАГ 3]: Спрашиваем ИИ...")
        ai_movies = await get_ai_movie_recommendations(query_clean)
        print(f"🤖 [DEBUG ШАГ 3]: ИИ порекомендовал: {ai_movies}")
        
        if ai_movies:
            results = []
            tasks = [tmdb.search_movies(m.get("title", ""), page=1) for m in ai_movies if isinstance(m, dict) and m.get("title")]
            tmdb_responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, res in enumerate(tmdb_responses):
                if isinstance(res, Exception): continue
                items = res.get("results", []) if isinstance(res, dict) else res
                
                if items and isinstance(items, list) and len(items) > 0:
                    best_match = _pick_ai_match(items, ai_movies[i])
                    if best_match is not None:
                        results.append(best_match)
                    
            if results:
                print(f"✅ [DEBUG ШАГ 3]: Нашли {len(results)} точных постеров с проверкой года.")
                unique_results = []
                seen_results = set()
                for item in results:
                    key = (getattr(item, "movie_id", None), getattr(item, "media_type", None))
                    if key in seen_results:
                        continue
                    seen_results.add(key)
                    unique_results.append(item)
                await search_cache.put(cache_key, unique_results)
                return unique_results, "🧠 ИИ-Поиск"

    print(f"❌ [DEBUG ИТОГ]: НИЧЕГО НЕ НАЙДЕНО.")
    return [], "❌ Не найдено"


async def get_typed_search_results(query: str, search_type: str, page: int = 1):
    """Shared typed search used by Telegram and future HTTP clients."""
    if search_type not in {"movie", "tv"}:
        return [], "❌ Не найдено"
    try:
        if hasattr(tmdb, "search_media"):
            results = await tmdb.search_media(query.strip(), search_type, page=page, limit=5)
        else:
            results = await tmdb.search_movies(query.strip(), page=page, limit=20)
        filtered = [item for item in results if getattr(item, "media_type", None) == search_type]
        return filtered[:5], "🔍 TMDB"
    except Exception:
        logging.exception("Typed search failed")
        return [], "❌ Сервис поиска недоступен"


async def get_person_search_results(query: str, page: int = 1):
    try:
        return (await tmdb.search_people(query.strip(), page=page, limit=5))[:5], "👤 TMDB"
    except Exception:
        logging.exception("Person search failed")
        return [], "❌ Сервис поиска недоступен"


async def get_unified_search_results(query: str, page: int = 1):
    """Return one bounded result set for titles and people."""
    try:
        if hasattr(tmdb, "search_all"):
            results = await tmdb.search_all(query.strip(), page=page, limit=5)
        else:
            media, people = await asyncio.gather(
                tmdb.search_movies(query.strip(), page=page, limit=5),
                tmdb.search_people(query.strip(), page=page, limit=5),
            )
            results = list(media) + list(people)
        return results[:5], "🔍 TMDB"
    except Exception:
        logging.exception("Unified search failed")
        return [], "❌ Сервис поиска недоступен"
