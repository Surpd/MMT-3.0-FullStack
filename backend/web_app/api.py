from aiohttp import web
from config import db, recommendation_service, session_cache, daily_cache, bot, WEBAPP_URL, tmdb
from datetime import datetime
import logging
from time import perf_counter
from services.quiz_service import QuizService, SESSION_SIZES
from services.stats_service import stats_service
from services.search_service import get_search_results
from services.library_service import get_webapp_library_data
from services.tags_service import get_user_personalized_tags
from web_app.serializers import serialize_movie_for_webapp
from models.movie_model import MovieModel
from services.tv_notification_service import run_tv_notification_scan
from services.taste_service import get_taste_summary
from services.media_state_service import apply_media_state, apply_rating

logger = logging.getLogger(__name__)

def _request_user_id(request, supplied_user_id=None) -> int | None:
    authenticated_user_id = request.get("authenticated_user_id")
    if authenticated_user_id is None and not request.get("local_dev"):
        return None

    if supplied_user_id is None:
        return authenticated_user_id

    if isinstance(supplied_user_id, bool):
        return None
    try:
        requested_user_id = int(supplied_user_id)
    except (TypeError, ValueError):
        return None

    if requested_user_id <= 0:
        return None
    if authenticated_user_id is not None and requested_user_id != authenticated_user_id:
        raise web.HTTPForbidden(text="user_id does not match authenticated Telegram user")
    return requested_user_id


def _parse_bounded_int(value, name: str, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if str(value).strip() != str(parsed) or not minimum <= parsed <= maximum:
        return None
    return parsed


def _parse_rating(value) -> int | None:
    return _parse_bounded_int(value, "rating", 1, 5)


def _parse_media_type(value) -> str | None:
    return value if value in ("movie", "tv") else None


def _has_local_detail_metadata(movie_data: dict | None, media_type: str) -> bool:
    if not isinstance(movie_data, dict) or movie_data.get("media_type", media_type) != media_type:
        return False
    if not movie_data.get("title") and not movie_data.get("name"):
        return False
    return bool(
        movie_data.get("overview")
        or movie_data.get("actors")
        or movie_data.get("directors")
        or movie_data.get("runtime_mins")
        or (media_type == "tv" and movie_data.get("seasons"))
    )


def _merge_recommendation_tv_metadata(movie_row: dict, recommendation: dict) -> dict:
    """Keep canonical DB data, filling incomplete TV metadata from the same recommendation."""
    media_type = movie_row.get("media_type") or recommendation.get("media_type")
    if media_type != "tv":
        return movie_row
    merged = dict(movie_row)
    if not merged.get("media_type"):
        merged["media_type"] = media_type
    if not isinstance(merged.get("seasons"), int) or merged.get("seasons", 0) <= 0:
        if isinstance(recommendation.get("seasons"), int) and recommendation["seasons"] > 0:
            merged["seasons"] = recommendation["seasons"]
    if not isinstance(merged.get("tv_status"), str) or not merged["tv_status"].strip():
        if isinstance(recommendation.get("tv_status"), str) and recommendation["tv_status"].strip():
            merged["tv_status"] = recommendation["tv_status"]
    return merged


async def handle_tv_notifications_job(request):
    summary = await run_tv_notification_scan(db, bot, WEBAPP_URL)
    status = 409 if summary.get("busy") else (200 if summary.get("ok") else 500)
    return web.json_response(summary, status=status)

async def handle_swipe(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    user_id = _request_user_id(request, payload.get("user_id"))
    movie_id = _parse_bounded_int(payload.get("movie_id"), "movie_id", 1, 2_000_000_000)
    action = payload.get("action")
    media_type = _parse_media_type(payload.get("media_type", "movie"))
    action_id = payload.get("action_id")
    if action_id is not None and (not isinstance(action_id, str) or not 1 <= len(action_id) <= 128):
        return web.json_response({"ok": False, "error": "invalid_action_id"}, status=400)
    status_map = {"liked": "liked", "archive": "archive", "watchlist": "watchlist", "dislike": "archive", "skip": "archive"}
    status = status_map.get(action)

    if not all([user_id, movie_id, status, media_type]):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

    movie_exists = await db.get_movie(movie_id, media_type)
    if not movie_exists:
        try:
            from services.movie_service import ensure_movie_in_db
            await ensure_movie_in_db(movie_id, media_type)
        except: pass

    result = await apply_media_state(
        db, recommendation_service, user_id, movie_id, media_type, status, action_id=action_id
    )
    return web.json_response({"ok": True, "duplicate": result["duplicate"]})


async def handle_set_rating(request):
    try: payload = await request.json()
    except Exception: return web.json_response({"ok": False}, status=400)

    user_id = _request_user_id(request, payload.get("user_id"))
    movie_id = _parse_bounded_int(payload.get("movie_id"), "movie_id", 1, 2_000_000_000)
    rating = _parse_rating(payload.get("rating"))
    media_type = _parse_media_type(payload.get("media_type", "movie"))

    if not all([user_id, movie_id, rating, media_type]):
        return web.json_response({"ok": False}, status=400)

    # 1. ГАРАНТИРУЕМ наличие фильма в БД перед оценкой (иначе ForeignKey error)
    try:
        from services.movie_service import ensure_movie_in_db
        await ensure_movie_in_db(movie_id, media_type)
    except Exception as e: pass

    await apply_rating(db, recommendation_service, user_id, movie_id, media_type, rating)
    return web.json_response({"ok": True})


def _parse_recommendation_filters(request):
    target_type = request.query.get("target_type", "mix")
    if target_type not in ("mix", "movie", "tv"):
        raise web.HTTPBadRequest(text="invalid target_type")

    min_year = None
    max_year = None
    min_rating = None
    if request.query.get("min_year") is not None:
        try:
            min_year = _parse_bounded_int(
                request.query.get("min_year"), "min_year", 1888, datetime.now().year + 2
            )
            if min_year is None:
                raise web.HTTPBadRequest(text="invalid min_year")
        except (TypeError, ValueError):
            raise web.HTTPBadRequest(text="invalid min_year")
    if request.query.get("max_year") is not None:
        max_year = _parse_bounded_int(
            request.query.get("max_year"), "max_year", 1888, datetime.now().year + 2
        )
        if max_year is None:
            raise web.HTTPBadRequest(text="invalid max_year")
    if min_year is not None and max_year is not None and min_year > max_year:
        raise web.HTTPBadRequest(text="min_year must be <= max_year")
    if request.query.get("min_rating") is not None:
        try:
            min_rating = float(request.query.get("min_rating"))
            if not 0 <= min_rating <= 10:
                raise web.HTTPBadRequest(text="invalid min_rating")
        except (TypeError, ValueError):
            raise web.HTTPBadRequest(text="invalid min_rating")

    return target_type, min_year, max_year, min_rating


async def _build_recommendations_response(user_id: int, cursor: int, target_type: str, min_year, max_year, min_rating, force_refresh: bool = False):
    if cursor == 0:
        await recommendation_service.invalidate_user_cache(user_id)

    raw_recs, is_new_pool = await recommendation_service.get_next_movies(
        int(user_id),
        cursor,
        force_refresh=force_refresh or cursor == 0,
        target_type=target_type,
        min_year=min_year,
        max_year=max_year,
        min_rating=min_rating,
    )

    if len(raw_recs) == 0 and not force_refresh:
        await recommendation_service.invalidate_user_cache(user_id)
        raw_recs, is_new_pool = await recommendation_service.get_next_movies(
            int(user_id),
            cursor,
            force_refresh=True,
            target_type=target_type,
            min_year=min_year,
            max_year=max_year,
            min_rating=min_rating,
        )

    movie_ids = [rec["movie_id"] for rec in raw_recs if rec.get("movie_id")]
    movies_data = []

    if movie_ids:
        query = db._client.table("movies").select("*").in_("id", movie_ids)
        response = await db._execute(query)
        local_movies = {(row["id"], row.get("media_type") or "movie"): row for row in (response.data or [])}

        for rec in raw_recs:
            m_id = rec.get("movie_id")
            movie_row = local_movies.get((m_id, rec.get("media_type") or "movie")) or rec
            if movie_row:
                movie_row = _merge_recommendation_tv_metadata(movie_row, rec)
                movie_obj = MovieModel.from_dict(movie_row, reason=rec.get("reason", ""))
                movies_data.append(serialize_movie_for_webapp(movie_obj))

    next_cursor = len(raw_recs) if is_new_pool else cursor + len(raw_recs)
    return {"ok": True, "movies": movies_data, "next_cursor": next_cursor}


async def handle_get_recommendations(request):
    user_id = _request_user_id(request, request.query.get("user_id"))
    skip = _parse_bounded_int(request.query.get("skip", "0"), "skip", 0, 10_000)

    if not user_id or skip is None:
        return web.json_response({"ok": False, "error": "missing user_id"}, status=400)

    target_type, min_year, max_year, min_rating = _parse_recommendation_filters(request)
    payload = await _build_recommendations_response(user_id, skip, target_type, min_year, max_year, min_rating)
    return web.json_response(payload)


async def handle_get_movies(request):
    user_id = _request_user_id(request, request.query.get("user_id"))
    cursor = _parse_bounded_int(request.query.get("cursor", "0"), "cursor", 0, 10_000)

    if not user_id or cursor is None:
        return web.json_response({"ok": False, "error": "missing user_id"}, status=400)

    if cursor == 0:
        await recommendation_service.invalidate_user_cache(user_id)

    raw_recs, is_new_pool = await recommendation_service.get_next_movies(int(user_id), cursor, force_refresh=cursor == 0)
    print(f"DEBUG: User {user_id} requested movies. Cursor: {cursor}. Raw recs length: {len(raw_recs)}")

    if len(raw_recs) == 0:
        print(f"DEBUG: No candidates found for user {user_id}. Check recommendation_service logic.")
        await recommendation_service.invalidate_user_cache(user_id)
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
        local_movies = {(row["id"], row.get("media_type") or "movie"): row for row in (response.data or [])}
        
        # Собираем итоговый массив
        for rec in raw_recs:
            m_id = rec.get("movie_id")
            movie_row = local_movies.get((m_id, rec.get("media_type") or "movie")) or rec
            if movie_row:
                movie_row = _merge_recommendation_tv_metadata(movie_row, rec)
                movie_obj = MovieModel.from_dict(movie_row, reason=rec.get("reason", ""))
                movies_data.append(serialize_movie_for_webapp(movie_obj))

    next_cursor = len(raw_recs) if is_new_pool else cursor + len(raw_recs)
    
    # ВОТ ЭТОТ RETURN БЫЛ ПОТЕРЯН
    return web.json_response({"ok": True, "movies": movies_data, "next_cursor": next_cursor})

async def handle_get_library(request):
    started_at = perf_counter()
    user_id = _request_user_id(request, request.query.get("user_id"))
    status = request.query.get("status", "liked")
    page = _parse_bounded_int(request.query.get("page", "1"), "page", 1, 1_000)
    if not user_id or page is None or status not in ("liked", "watchlist", "archive"):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)
    
    limit = 100
    offset = (page - 1) * limit
    
    # 1. Получаем список ID сохраненных фильмов пользователя
    db_started_at = perf_counter()
    raw_rows, total = await db.get_webapp_library(int(user_id), status, offset, limit)
    db_ms = (perf_counter() - db_started_at) * 1000
    
    if not raw_rows:
        response = web.json_response({"ok": True, "movies": [], "total": total})
        logger.info(
            "[library-timing] status=%s page=%s rows=0 total=%s db_ms=%.1f join_ms=0 tv_ms=0 payload_bytes=%s total_ms=%.1f queries=2",
            status,
            page,
            total,
            db_ms,
            len(response.body or b""),
            (perf_counter() - started_at) * 1000,
        )
        return response
        
    # The relation join already contains the catalog row. Do not fetch movies again.
    join_started_at = perf_counter()
    local_movies: dict[tuple[int, str], dict] = {}
    for row in raw_rows:
        joined = row.get("movies")
        if isinstance(joined, list):
            joined = joined[0] if joined else None
        if not isinstance(joined, dict):
            continue
        movie_id = row.get("movie_id")
        media_type = row.get("media_type") or "movie"
        if movie_id:
            local_movies[(movie_id, media_type)] = joined
    join_ms = (perf_counter() - join_started_at) * 1000

    final_movies = []
    tv_ids = [row.get("movie_id") for row in raw_rows if row.get("media_type") == "tv" and row.get("movie_id")]
    from services.tv_service import get_tv_progress_summaries
    tv_metadata = {
        movie_id: local_movies[(movie_id, "tv")]
        for movie_id in tv_ids
        if (movie_id, "tv") in local_movies
    }
    tv_started_at = perf_counter()
    tv_progress = await get_tv_progress_summaries(
        int(user_id),
        tv_ids,
        ensure_metadata=False,
        metadata_by_tv_id=tv_metadata,
    )
    tv_ms = (perf_counter() - tv_started_at) * 1000
    for row in raw_rows:
        m_id = row.get("movie_id")
        movie_data = local_movies.get((m_id, row.get("media_type") or "movie"))
        if not movie_data:
            continue
        
        # 1. Сначала пропускаем через жесткий сериализатор
        serialized = serialize_movie_for_webapp(movie_data)
        
        # 2. ПРИНУДИТЕЛЬНО добавляем наши поля поверх очищенного словаря
        serialized["user_status"] = row.get("status")
        serialized["user_rating"] = row.get("rating") or 0
        if m_id in tv_progress:
            summary = tv_progress[m_id]
            if summary["caught_up"] and movie_data.get("tv_status") in {"Ended", "Canceled", "Завершен"}:
                summary = {**summary, "completed": True, "state": "completed"}
            serialized["tv_progress"] = summary
        
        final_movies.append(serialized)
        
    response = web.json_response({"ok": True, "movies": final_movies, "total": total})
    logger.info(
        "[library-timing] status=%s page=%s rows=%s total=%s db_ms=%.1f join_ms=%.1f tv_ms=%.1f payload_bytes=%s total_ms=%.1f queries=%s",
        status,
        page,
        len(final_movies),
        total,
        db_ms,
        join_ms,
        tv_ms,
        len(response.body or b""),
        (perf_counter() - started_at) * 1000,
        2 + (3 if tv_ids else 0),
    )
    return response

async def handle_search(request):
    q = (request.query.get("q") or "").strip()

    # Защита от огромных текстов: жестко режем до 100 символов
    q = q[:100]

    user_id = _request_user_id(request, request.query.get("user_id"))

    if user_id is None:
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
    user_id = _request_user_id(request, request.query.get("user_id"))
    if user_id is None:
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

    tags = await get_user_personalized_tags(user_id)
    
    return web.json_response({"tags": tags})

async def handle_get_taste_summary(request):
    user_id = _request_user_id(request, request.query.get("user_id"))
    if user_id is None:
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)
    return web.json_response({"ok": True, **await get_taste_summary(user_id)})

async def handle_get_movie_details(request):
    movie_id = _parse_bounded_int(request.query.get("movie_id"), "movie_id", 1, 2_000_000_000)
    user_id = _request_user_id(request, request.query.get("user_id"))
    media_type = _parse_media_type(request.query.get("media_type", "movie"))
    if not movie_id or not user_id: return web.json_response({"ok": False}, status=400)
    if media_type is None:
        return web.json_response({"ok": False, "error": "invalid_media_type"}, status=400)

    # 1. Local-first: the library/search payload is already sufficient for the first render.
    from services.movie_service import ensure_movie_in_db
    movie_data = await db.get_movie(movie_id, media_type)
    if not _has_local_detail_metadata(movie_data, media_type):
        try:
            await ensure_movie_in_db(movie_id, media_type)
        except Exception as e:
            print(f"Error fetching to db: {e}")
        movie_data = await db.get_movie(movie_id, media_type)
    if not movie_data or movie_data.get("media_type", "movie") != media_type:
        return web.json_response({"ok": False}, status=404)

    # 3. Подтягиваем оценку юзера, если она есть
    user_movie = await db.get_user_movie(user_id, movie_id, media_type)
    user_status = user_movie.status if user_movie else None
    user_rating = (user_movie.rating or 0) if user_movie else 0
    if user_movie:
        movie_data["user_rating"] = user_rating
        movie_data["user_status"] = user_status

    response = {
        "ok": True,
        "movie": serialize_movie_for_webapp(movie_data),
        "user_status": user_status,
        "user_rating": user_rating,
    }
    if media_type == "tv":
        from services.tv_service import get_tv_progress
        response["tv_progress"] = await get_tv_progress(user_id, movie_id)
    return web.json_response(response)


async def handle_get_tv_progress(request):
    user_id = _request_user_id(request, request.query.get("user_id"))
    tv_id = _parse_bounded_int(request.query.get("tv_id"), "tv_id", 1, 2_000_000_000)
    if not user_id or not tv_id:
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)
    from services.tv_service import refresh_tv_metadata, get_tv_progress
    metadata = await refresh_tv_metadata(tv_id)
    if not metadata or metadata.get("media_type") != "tv":
        return web.json_response({"ok": False, "error": "tv_not_found"}, status=404)
    return web.json_response({"ok": True, "progress": await get_tv_progress(user_id, tv_id)})


async def handle_get_tv_season(request):
    user_id = _request_user_id(request, request.query.get("user_id"))
    tv_id = _parse_bounded_int(request.query.get("tv_id"), "tv_id", 1, 2_000_000_000)
    season = _parse_bounded_int(request.query.get("season_number"), "season_number", 1, 1000)
    if not user_id or tv_id is None or season is None:
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)
    from services.tv_service import get_tv_season_progress, refresh_tv_metadata
    metadata = await refresh_tv_metadata(tv_id)
    if not metadata or metadata.get("media_type") != "tv":
        return web.json_response({"ok": False, "error": "tv_not_found"}, status=404)
    if season > int(metadata.get("seasons") or 0):
        return web.json_response({"ok": False, "error": "season_not_found"}, status=404)
    season_data = await get_tv_season_progress(user_id, tv_id, season)
    if not season_data:
        return web.json_response({"ok": False, "error": "season_not_found"}, status=404)
    return web.json_response({"ok": True, "season": season_data})


async def handle_set_tv_episode_progress(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    user_id = _request_user_id(request, payload.get("user_id"))
    values = [payload.get(k) for k in ("tv_id", "season_number", "episode_number")]
    parsed = [_parse_bounded_int(v, k, 0 if k == "season_number" else 1, 2_000_000_000) for k, v in zip(("tv_id", "season_number", "episode_number"), values)]
    if not user_id or any(v is None for v in parsed) or not isinstance(payload.get("watched"), bool):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)
    try:
        from services.tv_service import refresh_tv_metadata, set_episode_watched
        metadata = await refresh_tv_metadata(parsed[0])
        if not metadata or metadata.get("media_type") != "tv":
            return web.json_response({"ok": False, "error": "tv_not_found"}, status=404)
        if parsed[1] > int(metadata.get("seasons") or 0):
            return web.json_response({"ok": False, "error": "season_not_found"}, status=404)
        progress = await set_episode_watched(user_id, parsed[0], parsed[1], parsed[2], payload["watched"])
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)
    return web.json_response({"ok": True, "progress": progress})


async def handle_set_tv_season_progress(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    user_id = _request_user_id(request, payload.get("user_id"))
    tv_id = _parse_bounded_int(payload.get("tv_id"), "tv_id", 1, 2_000_000_000)
    season = _parse_bounded_int(payload.get("season_number"), "season_number", 0, 1000)
    if not user_id or tv_id is None or season is None or not isinstance(payload.get("watched"), bool):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)
    from services.tv_service import refresh_tv_metadata, set_season_watched
    metadata = await refresh_tv_metadata(tv_id)
    if not metadata or metadata.get("media_type") != "tv":
        return web.json_response({"ok": False, "error": "tv_not_found"}, status=404)
    if season > int(metadata.get("seasons") or 0):
        return web.json_response({"ok": False, "error": "season_not_found"}, status=404)
    return web.json_response({"ok": True, "progress": await set_season_watched(user_id, tv_id, season, payload["watched"])})


async def handle_set_tv_notifications(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    user_id = _request_user_id(request, payload.get("user_id"))
    tv_id = _parse_bounded_int(payload.get("tv_id"), "tv_id", 1, 2_000_000_000)
    if not user_id or tv_id is None or not isinstance(payload.get("enabled"), bool):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)
    await db.set_tv_notification_subscription(user_id, tv_id, payload["enabled"])
    return web.json_response({"ok": True, "enabled": payload["enabled"]})


async def handle_get_stats(request):
    try:
        user_id = _request_user_id(request, request.query.get("user_id"))
        if not user_id:
            return web.json_response({"ok": False}, status=400)

        stats = await db.get_user_stats(int(user_id))
        if not stats:
            stats = {"points": 0, "quiz_total": 0, "quiz_correct": 0, "current_streak": 0, "best_streak": 0}

        level, title = stats_service.get_level_info(stats.get("points", 0))
        return web.json_response({"ok": True, "stats": stats, "level": level, "title": title})
    except Exception:
        logger.exception("stats retrieval failed")
        return web.json_response({"ok": False, "error": "stats_unavailable"}, status=500)


async def handle_get_quiz(request):
    try:
        user_id = _request_user_id(request)
        if user_id is None:
            return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)
        mode = request.query.get("mode", "cinema")
        if mode not in SESSION_SIZES:
            return web.json_response({"ok": False, "error": "invalid_mode"}, status=400)
        quiz_data = await QuizService(db, tmdb, session_cache, daily_cache).create_session(user_id, mode=mode)
        if not quiz_data:
            return web.json_response({"ok": False, "error": "quiz_not_available"}, status=404)
        return web.json_response({"ok": True, "quiz": quiz_data})
    except Exception:
        logger.exception("quiz session generation failed")
        return web.json_response({"ok": False, "error": "quiz_not_available"}, status=500)


async def handle_quiz_answer(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    user_id = _request_user_id(request, payload.get("user_id"))
    quiz_id = payload.get("quiz_id") or payload.get("session_id")
    answer = payload.get("answer")

    if user_id is None or not isinstance(quiz_id, str) or not 1 <= len(quiz_id) <= 128 or not isinstance(answer, str) or not 1 <= len(answer) <= 500:
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

    question_id = payload.get("question_id")
    if "question_id" in payload and (not isinstance(question_id, str) or not 1 <= len(question_id) <= 128):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)
    if isinstance(question_id, str) and question_id:
        elapsed_ms = payload.get("elapsed_ms")
        if elapsed_ms is not None and (isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, int) or not 0 <= elapsed_ms <= 120_000):
            return web.json_response({"ok": False, "error": "invalid_elapsed_ms"}, status=400)
        result = await QuizService(db, tmdb, session_cache, daily_cache).answer_session(user_id, quiz_id, question_id, answer, elapsed_ms)
        if not result:
            return web.json_response({"ok": False, "error": "invalid_quiz"}, status=400)
        level, title = stats_service.get_level_info(result["stats"].get("points", 0))
        return web.json_response({"ok": True, **result, "level": level, "title": title})

    quiz_key = f"quiz_{user_id}_{quiz_id}"
    quiz_data = await session_cache.get(quiz_key)
    if not isinstance(quiz_data, dict) or answer not in quiz_data.get("options", []):
        return web.json_response({"ok": False, "error": "invalid_quiz"}, status=400)
    await session_cache.delete(quiz_key)
    is_correct = answer == quiz_data.get("correct")

    current_stats = await db.get_user_stats(user_id) or {}
    new_stats, result_msg, xp_earned = stats_service.process_quiz_answer(is_correct, current_stats)
    await db.update_user_stats(user_id, new_stats)
    level, title = stats_service.get_level_info(new_stats.get("points", 0))

    return web.json_response({
        "ok": True,
        "message": result_msg,
        "stats": new_stats,
        "level": level,
        "title": title,
        "is_correct": is_correct,
        "correct_answer": quiz_data.get("correct"),
        "xp_earned": xp_earned,
    })
