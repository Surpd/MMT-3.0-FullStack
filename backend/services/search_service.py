from config import tmdb, search_cache

async def get_search_results(query: str, page: int = 1):
    """
    Получает данные. Возвращает кортеж (результаты, источник).
    """
    query_clean = query.strip().lower()
    cache_key = f"{query_clean}_{page}"
    
    # 1. Кэш
    cached = await search_cache.get(cache_key)
    if cached:
        return cached, "⚡ RAM"
    
    # 2. TMDB
    results = await tmdb.search_movies(query_clean, page=page)
    
    # 3. Сохранение
    if results:
        await search_cache.put(cache_key, results)
        
    return results, "🔍 TMDB"