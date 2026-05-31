from aiohttp import web
from config import db, recommendation_service, session_cache, recs_pool_cache
from services.library_service import get_webapp_library_data
from web_app.serializers import serialize_movie_for_webapp
from models.movie_model import MovieModel

async def handle_swipe(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    user_id = payload.get("user_id")
    movie_id = payload.get("movie_id")
    action = payload.get("action")
    status_map = {"liked": "liked", "archive": "archive", "watchlist": "watchlist", "dislike": "archive", "skip": "archive"}
    status = status_map.get(action)

    if not all([user_id, movie_id, status]):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

    movie_exists = await db.get_movie(movie_id)
    if not movie_exists:
        try:
            from services.movie_service import ensure_movie_in_db
            await ensure_movie_in_db(int(movie_id), payload.get("media_type", "movie"))
        except: pass

    await db.upsert_user_movie(user_id=user_id, movie_id=movie_id, status=status)
    return web.json_response({"ok": True})


async def handle_get_movies(request):
    user_id = request.query.get("user_id")
    cursor = int(request.query.get("cursor", 0))

    if not user_id:
        return web.json_response({"ok": False, "error": "missing user_id"}, status=400)

    if cursor == 0:
        await recs_pool_cache.delete(f"user_recs_pool_{user_id}")

    raw_recs, is_new_pool = await recommendation_service.get_next_movies(int(user_id), cursor)
    
    movie_ids = [rec["movie_id"] for rec in raw_recs if rec.get("movie_id")]
    movies_data = []
    
    if movie_ids:
        # Достаем то, что уже есть в базе
        query = db._client.table("movies").select("*").in_("id", movie_ids)
        response = await db._execute(query)
        local_movies = {row["id"]: row for row in (response.data or [])}
        
        # Ищем фильмы, которых не хватает в нашей БД
        missing_recs = [rec for rec in raw_recs if rec.get("movie_id") and rec["movie_id"] not in local_movies]
        
        if missing_recs:
            from services.movie_service import ensure_movie_in_db
            import asyncio
            
            # Скачиваем недостающие фильмы параллельно
            tasks = [ensure_movie_in_db(rec["movie_id"], rec.get("media_type", "movie")) for rec in missing_recs]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Делаем повторный запрос, чтобы забрать свежескачанные фильмы
            missing_ids = [rec["movie_id"] for rec in missing_recs]
            query_new = db._client.table("movies").select("*").in_("id", missing_ids)
            response_new = await db._execute(query_new)
            for row in (response_new.data or []):
                local_movies[row["id"]] = row
        
        # Собираем итоговый массив
        for rec in raw_recs:
            m_id = rec.get("movie_id")
            if m_id in local_movies:
                movie_obj = MovieModel.from_dict(local_movies[m_id], reason=rec.get("reason", ""))
                movies_data.append(serialize_movie_for_webapp(movie_obj))

    next_cursor = len(raw_recs) if is_new_pool else cursor + len(raw_recs)
    
    # ВОТ ЭТОТ RETURN БЫЛ ПОТЕРЯН
    return web.json_response({"ok": True, "movies": movies_data, "next_cursor": next_cursor})

async def handle_get_library(request):
    user_id = request.query.get("user_id")
    status = request.query.get("status", "liked")
    page = int(request.query.get("page", 1))
    
    formatted_movies, _, _ = await get_webapp_library_data(int(user_id), status, page, 100)
    
    final_movies = []
    for m in formatted_movies:
        # Данные из Supabase часто лежат внутри ключа 'movies' при join-запросах
        movie_data = m.get("movies", m)
        # Принудительно сохраняем ID, чтобы свайпы не сломались
        movie_data["movie_id"] = m.get("movie_id") or movie_data.get("id")
        
        # Пропускаем через "таможню" (тут добавятся актеры, время, абсолютные ссылки на постеры)
        final_movies.append(serialize_movie_for_webapp(movie_data))
        
    return web.json_response({"ok": True, "movies": final_movies})

async def handle_get_movie_details(request):
    movie_id = request.query.get("movie_id")
    user_id = request.query.get("user_id")
    if not movie_id or not user_id: return web.json_response({"ok": False}, status=400)

    movie_data = await db.get_movie(int(movie_id))
    if not movie_data: return web.json_response({"ok": False}, status=404)

    # 1. Делегируем проверку и обогащение сервису (API ничего не качает и не сохраняет сам)
    from services.movie_service import ensure_movie_in_db
    await ensure_movie_in_db(int(movie_id), movie_data.get("media_type", "movie"))
    
    # 2. Перечитываем свежую, 100% полную запись из базы
    movie_data = await db.get_movie(int(movie_id))
    if not movie_data:
        return web.json_response({"ok": False}, status=404)
        
    # 3. Превращаем в каноническую модель
    movie_obj = MovieModel.from_dict(movie_data)

    user_movie = await db.get_user_movie(int(user_id), int(movie_id))
    # Пропускаем детальную информацию через единый канонический контракт
    final_movie = serialize_movie_for_webapp(movie_obj)

    return web.json_response({
        "ok": True,
        "movie": final_movie,
        "user_status": user_movie.status if user_movie else "none",
        "user_rating": user_movie.rating if user_movie else 0
    })
