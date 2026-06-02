import re
import json
import asyncio
import aiohttp
from config import tmdb, search_cache
from utils.genres import TMDB_GENRES

# Вставь сюда свой ключ от Groq (если есть)
GROQ_API_KEY = "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"

GENRE_MAP = {
    "боевик": 28, "приключен": 12, "мульт": 16, "комед": 35, "криминал": 80,
    "документал": 99, "драм": 18, "семейн": 10751, "фэнтез": 14, "истор": 36,
    "ужас": 27, "музык": 10402, "детектив": 9648, "мелодрам": 10749,
    "фантастик": 878, "триллер": 53, "военн": 10752, "вестерн": 37
}

async def get_ai_movie_recommendations(query: str):
    if not GROQ_API_KEY: return []
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    system_prompt = (
        "Ты киноман и эксперт. Твоя задача — найти до 10 фильмов, которые максимально точно подходят под описание пользователя. "
        "Отсортируй выдачу по порядку: на первые места ставь самые релевантные и известные совпадения и высокий рейтинг, а дальше — менее популярные, но идеально подходящие по смыслу. "
        "Обязательно используй точные официальные русские названия. Делай акцент на российского пользователя "
        "Верни строго JSON с ключом 'movies'. Это должен быть массив объектов с 'title' (название) и 'year' (год выхода). "
        "Пример: {\"movies\": [{\"title\": \"Твоё имя\", \"year\": 2016}, {\"title\": \"Мальчик в девочке\", \"year\": 2006}]}. Никакого лишнего текста."
    )
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
        "temperature": 0.5
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    print(f"❌ [DEBUG AI]: Ошибка {resp.status} - {await resp.text()}")
                    return []
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                
                # Бронебойный парсинг JSON: вырезаем только то, что внутри { }
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    return json.loads(match.group(0)).get("movies", [])
                return []
    except Exception as e:
        print(f"❌ [DEBUG AI EXCEPTION]: {e}")
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
                    target_year = str(ai_movies[i].get("year", ""))
                    best_match = None
                    
                    # Ищем фильм, у которого совпадает год (первые 4 символа из release_date)
                    if target_year and target_year.isdigit():
                        for item in items:
                            # Универсальное получение даты (и для словарей, и для объектов)
                            release_date = item.get("release_date", "") if isinstance(item, dict) else getattr(item, "release_date", "")
                            
                            # Приводим к строке (защита от None) и сравниваем
                            if str(release_date).startswith(target_year):
                                best_match = item
                                break
                    
                    # Если точный год не найден (вдруг ИИ ошибся на 1 год), берем первый по популярности
                    if not best_match:
                        best_match = items[0]
                        
                    results.append(best_match)
                    
            if results:
                print(f"✅ [DEBUG ШАГ 3]: Нашли {len(results)} точных постеров с проверкой года.")
                await search_cache.put(cache_key, results)
                return results, "🧠 ИИ-Поиск"

    print(f"❌ [DEBUG ИТОГ]: НИЧЕГО НЕ НАЙДЕНО.")
    return [], "❌ Не найдено"