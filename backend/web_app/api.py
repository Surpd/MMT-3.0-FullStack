from aiohttp import web
from config import db, recommendation_service, session_cache, recs_pool_cache, tmdb
from services.library_service import get_webapp_library_data
async def handle_swipe(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    user_id = payload.get("user_id")
    movie_id = payload.get("movie_id")
    action = payload.get("action")

    status_map = {
        "liked": "liked", 
        "archive": "archive", 
        "watchlist": "watchlist",
        "dislike": "archive",
        "ignored": "archive",
        "skip": "archive"
    }

    status = status_map.get(action)

    if user_id is None or movie_id is None or status is None:
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

    media_type = payload.get("media_type", "movie")
    genre_ids = payload.get("genre_ids", [])

    # 1. Проверяем, есть ли фильм в нашей БД
    movie_exists = await db.get_movie(movie_id)
    if not movie_exists:
        try:
            movie_details = await tmdb.get_movie_details(movie_id, media_type=media_type)
            movie_data = {
                "id": movie_details.movie_id,
                "title": movie_details.title,
                "year": movie_details.year,
                "rating_numeric": movie_details.tmdb_rating,
                "overview": movie_details.overview,
                "poster_url": movie_details.poster_url,
                "genres_array": movie_details.genres,
                "media_type": movie_details.media_type
            }
            await db.save_movie(movie_data)
        except Exception as e:
            print(f"Ошибка при сохранении фильма {movie_id} из TMDB: {e}")
            return web.json_response({"ok": False, "error": "tmdb_fetch_failed"}, status=400)

    # 2. Пишем результат в базу
    await db.upsert_user_movie(user_id=user_id, movie_id=movie_id, status=status)

    # 3. РАБОТА С СЕССИЕЙ
    session_key = f"session_{user_id}"
    session_data = await session_cache.get(session_key) or {"skipped_genres": [], "skips_in_a_row": 0}

    if status == "archive":
        session_data["skips_in_a_row"] += 1
        session_data["skipped_genres"].extend(genre_ids)
        
        if session_data["skips_in_a_row"] >= 4:
            await recs_pool_cache.delete(f"user_recs_pool_{user_id}")
            session_data["skips_in_a_row"] = 0
            
    elif status == "liked":
        session_data["skips_in_a_row"] = 0

    session_data["skipped_genres"] = session_data["skipped_genres"][-20:]
    await session_cache.put(session_key, session_data)

    return web.json_response({"ok": True})

async def handle_get_movies(request):
    user_id = request.query.get("user_id")
    cursor = int(request.query.get("cursor", 0))

    if not user_id:
        return web.json_response({"ok": False, "error": "missing user_id"}, status=400)

    if cursor == 0:
        await recs_pool_cache.delete(f"user_recs_pool_{user_id}")

    movies, is_new_pool = await recommendation_service.get_next_movies(int(user_id), cursor)
    
    print(f"🚨 DEBUG: Для юзера {user_id} сгенерировано {len(movies)} фильмов. Новый пул: {is_new_pool}")
    
    next_cursor = len(movies) if is_new_pool else cursor + len(movies)

    return web.json_response({"ok": True, "movies": movies, "next_cursor": next_cursor})

# web_app/api.py
# (не забудь импортировать библиотечный сервис вверху файла: from services.library_service import get_webapp_library_data)

async def handle_get_library(request):
    user_id = request.query.get("user_id")
    status = request.query.get("status", "liked") 
    page = int(request.query.get("page", 1))
    limit = int(request.query.get("limit", 10))

    if not user_id:
        return web.json_response({"ok": False, "error": "missing user_id"}, status=400)

    # Просим у Сервиса готовое блюдо
    from services import library_service
    formatted_movies, total, total_pages = await library_service.get_webapp_library_data(
        int(user_id), status, page, limit
    )

    # Просто отдаем JSON
    return web.json_response({
        "ok": True,
        "movies": formatted_movies,
        "total": total,
        "page": page,
        "total_pages": total_pages
    })

async def handle_get_movie_details(request):
    movie_id = request.query.get("movie_id")
    user_id = request.query.get("user_id")

    if not movie_id or not user_id:
        return web.json_response({"ok": False, "error": "missing parameters"}, status=400)

    try:
        # 1. Идем в базу за полной инфой о фильме
        from config import db
        movie_query = db._client.table("movies").select("*").eq("id", movie_id).single()
        movie_response = await db._execute(movie_query)
        movie_data = movie_response.data if movie_response and movie_response.data else {}

        if not movie_data:
             return web.json_response({"ok": False, "error": "movie not found"}, status=404)

        # 2. Узнаем, какой статус у этого фильма у конкретного юзера
        status_query = db._client.table("user_movies").select("status, rating").eq("user_id", user_id).eq("movie_id", movie_id).single()
        status_response = await db._execute(status_query)
        user_status = status_response.data if status_response and status_response.data else {"status": "none", "rating": 0}

        return web.json_response({
            "ok": True,
            "movie": movie_data,
            "user_status": user_status.get("status", "none"),
            "user_rating": user_status.get("rating", 0)
        })
    except Exception as e:
        print(f"Ошибка в handle_get_movie_details: {e}")
        return web.json_response({"ok": False, "error": "server error"}, status=500)