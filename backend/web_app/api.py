from aiohttp import web
from config import db, recommendation_service, session_cache, recs_pool_cache, tmdb
from services.library_service import get_webapp_library_data

def format_poster(path):
    if not path: return ""
    if str(path).startswith("http"): return path
    return f"https://image.tmdb.org/t/p/w500{path}"

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
            details = await tmdb.get_movie_details(movie_id, media_type=payload.get("media_type", "movie"))
            await db.save_movie({
                "id": details.movie_id, "title": details.title, "year": details.year,
                "rating_numeric": details.tmdb_rating, "overview": details.overview,
                "poster_url": details.poster_url, "genres_array": details.genres,
                "media_type": details.media_type
            })
        except: pass

    await db.upsert_user_movie(user_id=user_id, movie_id=movie_id, status=status)
    return web.json_response({"ok": True})

async def handle_get_movies(request):
    user_id = request.query.get("user_id")
    cursor = int(request.query.get("cursor", 0))
    if not user_id: return web.json_response({"ok": False}, status=400)
    
    if cursor == 0: await recs_pool_cache.delete(f"user_recs_pool_{user_id}")
    movies, is_new_pool = await recommendation_service.get_next_movies(int(user_id), cursor)
    
    for m in movies or []:
        m["poster_path"] = format_poster(m.get("poster_path") or m.get("poster_url"))
    
    next_cursor = len(movies) if is_new_pool else cursor + len(movies)
    return web.json_response({"ok": True, "movies": movies, "next_cursor": next_cursor})

async def handle_get_library(request):
    user_id = request.query.get("user_id")
    status = request.query.get("status", "liked")
    page = int(request.query.get("page", 1))
    formatted_movies, _, _ = await get_webapp_library_data(int(user_id), status, page, 100)
    for m in formatted_movies:
        m["poster_path"] = format_poster(m.get("poster_path"))
    return web.json_response({"ok": True, "movies": formatted_movies})

async def handle_get_movie_details(request):
    movie_id = request.query.get("movie_id")
    user_id = request.query.get("user_id")
    if not movie_id or not user_id: return web.json_response({"ok": False}, status=400)

    movie_data = await db.get_movie(int(movie_id))
    if not movie_data: return web.json_response({"ok": False}, status=404)

    # ПРОВЕРКА НА ПОЛНОТУ (Refresh)
    has_cast = movie_data.get("actors") and len(movie_data.get("actors", [])) > 0
    if not movie_data.get("overview") or not has_cast:
        tmdb_ext = await (tmdb.get_movie_details_extended(int(movie_id)) if movie_data.get("media_type") != "tv" else tmdb.get_tv_details_extended(int(movie_id)))
        if tmdb_ext:
            credits = tmdb_ext.get("credits", {})
            movie_data.update({
                "overview": tmdb_ext.get("overview"),
                "actors": [a.get("name") for a in credits.get("cast", [])[:5]],
                "directors": [d.get("name") for d in credits.get("crew", []) if d.get("job") == "Director"],
                "runtime_mins": tmdb_ext.get("runtime") or (tmdb_ext.get("episode_run_time", [0])[0] if tmdb_ext.get("episode_run_time") else 0)
            })
            await db.save_movie(movie_data)

    user_movie = await db.get_user_movie(int(user_id), int(movie_id))
    return web.json_response({
        "ok": True,
        "movie": {
            **movie_data,
            "movie_id": movie_data.get("id"),
            "poster_path": format_poster(movie_data.get("poster_url") or movie_data.get("poster_path")),
            "genres": movie_data.get("genres_array") or []
        },
        "user_status": user_movie.status if user_movie else "none",
        "user_rating": user_movie.rating if user_movie else 0
    })