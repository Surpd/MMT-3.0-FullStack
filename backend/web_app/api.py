from aiohttp import web
from config import db, recommendation_service, session_cache, recs_pool_cache
from services.quiz_service import get_random_movie_id, build_quiz
from services.stats_service import stats_service
from services.search_service import get_search_results
from services.library_service import get_webapp_library_data
from services.tags_service import get_user_personalized_tags
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


async def handle_set_rating(request):
    try: payload = await request.json()
    except Exception: return web.json_response({"ok": False}, status=400)

    user_id = payload.get("user_id")
    movie_id = payload.get("movie_id")
    rating = payload.get("rating")
    media_type = payload.get("media_type", "movie")

    if not all([user_id, movie_id, rating]):
        return web.json_response({"ok": False}, status=400)

    # 1. ГАРАНТИРУЕМ наличие фильма в БД перед оценкой (иначе ForeignKey error)
    try:
        from services.movie_service import ensure_movie_in_db
        await ensure_movie_in_db(int(movie_id), media_type)
    except Exception as e: pass

    # 2. Получаем текущий статус, чтобы не затереть его (например, не выкинуть из watchlist)
    current = await db.get_user_movie(int(user_id), int(movie_id))
    status = current.status if current else "liked"

    # 3. Сохраняем оценку и восстанавливаем статус
    await db.upsert_user_movie(
        user_id=int(user_id), 
        movie_id=int(movie_id), 
        status=status, 
        media_type=media_type, 
        rating=int(rating)
    )
    return web.json_response({"ok": True})


async def handle_get_movies(request):
    user_id = request.query.get("user_id")
    cursor = int(request.query.get("cursor", 0))

    if not user_id:
        return web.json_response({"ok": False, "error": "missing user_id"}, status=400)

    if cursor == 0:
        await recs_pool_cache.delete(f"user_recs_pool_{user_id}")

    raw_recs, is_new_pool = await recommendation_service.get_next_movies(int(user_id), cursor)
    print(f"DEBUG: User {user_id} requested movies. Cursor: {cursor}. Raw recs length: {len(raw_recs)}")

    if len(raw_recs) == 0:
        print(f"DEBUG: No candidates found for user {user_id}. Check recommendation_service logic.")
        await recs_pool_cache.delete(f"user_recs_pool_{user_id}")
        raw_recs, is_new_pool = await recommendation_service.get_next_movies(int(user_id), cursor, force_refresh=True)
        print(f"DEBUG: Retry for user {user_id}. Raw recs length: {len(raw_recs)}")
        if len(raw_recs) == 0:
            print(f"DEBUG: Retry also returned empty pool for user {user_id}.")
    
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
    
    limit = 100
    offset = (page - 1) * limit
    
    # 1. Получаем список ID сохраненных фильмов пользователя
    raw_rows, _ = await db.get_webapp_library(int(user_id), status, offset, limit)
    
    if not raw_rows:
        return web.json_response({"ok": True, "movies": []})
        
    # 2. Вытаскиваем чистые ID
    movie_ids = [row.get("movie_id") for row in raw_rows if row.get("movie_id")]
    
    # 3. ЖЕЛЕЗОБЕТОННЫЙ ЗАПРОС: берем ВСЕ данные напрямую из таблицы movies (как в свайпах)
    query = db._client.table("movies").select("*").in_("id", movie_ids)
    response = await db._execute(query)
    local_movies = {r["id"]: r for r in (response.data or [])}
    
    final_movies = []
    for row in raw_rows:
        m_id = row.get("movie_id")
        movie_data = local_movies.get(m_id)
        if not movie_data:
            continue
        
        # 1. Сначала пропускаем через жесткий сериализатор
        serialized = serialize_movie_for_webapp(movie_data)
        
        # 2. ПРИНУДИТЕЛЬНО добавляем наши поля поверх очищенного словаря
        serialized["user_status"] = row.get("status")
        serialized["user_rating"] = row.get("rating") or 0
        
        final_movies.append(serialized)
        
    return web.json_response({"ok": True, "movies": final_movies})

async def handle_search(request):
    q = (request.query.get("q") or "").strip()

    # Защита от огромных текстов: жестко режем до 100 символов
    q = q[:100]

    user_id = request.query.get("user_id")

    try:
        int(user_id)
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

    if not q:
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

    results, _ = await get_search_results(q, page=1)
    final_movies = []

    for item in results or []:
        if not item:
            continue
        movie_obj = MovieModel.from_dict(item) if isinstance(item, dict) else item

        # Превращаем объект MovieSearchResult в словарь, который поймет фронтенд
        movie_dict = {
            "movie_id": movie_obj.movie_id,
            "title": movie_obj.title,
            "year": movie_obj.year,
            "media_type": movie_obj.media_type,
            "poster_path": movie_obj.poster_path or "",
            # Достаем vote_average из объекта или словаря
            "rating": getattr(movie_obj, 'vote_average', 0) or getattr(movie_obj, 'rating', 0) or (item.get("vote_average", 0) if isinstance(item, dict) else 0)
        }
        final_movies.append(movie_dict)

    return web.json_response({"ok": True, "movies": final_movies})

async def handle_get_search_tags(request):
    """Возвращает динамические теги для экрана поиска"""
    user_id_str = request.query.get("user_id")
    
    # Если user_id нет или он кривой, передаем None (служба вернет дефолтные)
    try:
        user_id = int(user_id_str) if user_id_str else None
    except ValueError:
        user_id = None
        
    tags = await get_user_personalized_tags(user_id)
    
    return web.json_response({"tags": tags})

async def handle_get_movie_details(request):
    movie_id = request.query.get("movie_id")
    user_id = request.query.get("user_id")
    media_type = request.query.get("media_type", "movie")
    if not movie_id or not user_id: return web.json_response({"ok": False}, status=400)

    # 1. Сначала гарантируем, что фильм скачан с TMDB в нашу БД со всеми актерами и хронометражем
    from services.movie_service import ensure_movie_in_db
    try:
        await ensure_movie_in_db(int(movie_id), media_type)
    except Exception as e:
        print(f"Error fetching to db: {e}")

    # 2. Теперь берем полные данные из базы
    movie_data = await db.get_movie(int(movie_id))
    if not movie_data:
        return web.json_response({"ok": False}, status=404)

    # 3. Подтягиваем оценку юзера, если она есть
    user_query = db._client.table("user_movies").select("*").eq("user_id", int(user_id)).eq("movie_id", int(movie_id))
    user_movie = await db._execute(user_query)
    user_status = None
    user_rating = 0
    if user_movie and user_movie.data:
        user_status = user_movie.data[0].get("status")
        user_rating = user_movie.data[0].get("rating") or 0
        movie_data["user_rating"] = user_rating
        movie_data["user_status"] = user_status

    return web.json_response({
        "ok": True,
        "movie": serialize_movie_for_webapp(movie_data),
        "user_status": user_status,
        "user_rating": user_rating,
    })


async def handle_get_stats(request):
    try:
        user_id = request.query.get("user_id")
        if not user_id:
            return web.json_response({"ok": False}, status=400)

        stats = await db.get_user_stats(int(user_id))
        if not stats:
            stats = {"points": 0, "quiz_total": 0, "quiz_correct": 0, "current_streak": 0, "best_streak": 0}

        level, title = stats_service.get_level_info(stats.get("points", 0))
        return web.json_response({"ok": True, "stats": stats, "level": level, "title": title})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def handle_get_quiz(request):
    try:
        movie_id = await get_random_movie_id()
        quiz_data = await build_quiz(movie_id)
        if not quiz_data:
            return web.json_response({"ok": False, "error": "quiz_not_available"}, status=404)
        return web.json_response({"ok": True, "quiz": quiz_data})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def handle_quiz_answer(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    user_id = payload.get("user_id")
    is_correct = bool(payload.get("correct", False))

    if user_id is None:
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)

    current_stats = await db.get_user_stats(user_id) or {}
    new_stats, result_msg = stats_service.process_quiz_answer(is_correct, current_stats)
    await db.update_user_stats(user_id, new_stats)
    level, title = stats_service.get_level_info(new_stats.get("points", 0))

    return web.json_response({
        "ok": True,
        "message": result_msg,
        "stats": new_stats,
        "level": level,
        "title": title,
    })
