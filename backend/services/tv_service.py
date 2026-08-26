from __future__ import annotations

from datetime import date, datetime, timezone
import asyncio
from typing import Any

from config import db, tmdb

TV_METADATA_TTL_DAYS = 1
SEASON_METADATA_TTL_DAYS = 7
_metadata_locks: dict[int, asyncio.Lock] = {}


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _is_released(air_date: str | None) -> bool:
    parsed = _parse_date(air_date)
    return parsed is not None and parsed <= date.today()


def choose_next_episode(episodes: list[dict], watched: set[tuple[int, int]]) -> dict | None:
    return next((e for e in episodes if _is_released(e.get("air_date")) and (e.get("season_number"), e.get("episode_number")) not in watched), None)


def compute_tv_state(user_status: str | None, watched_count: int, available_count: int, tv_status: str | None) -> str:
    caught_up = available_count > 0 and watched_count == available_count
    if not user_status:
        return "none"
    if not watched_count:
        return "watchlist" if user_status == "watchlist" else "none"
    if caught_up and tv_status in {"Ended", "Canceled", "Завершен"}:
        return "completed"
    return "caught_up" if caught_up else "watching"


async def refresh_tv_metadata(tv_id: int, force: bool = False) -> dict[str, Any] | None:
    lock = _metadata_locks.setdefault(tv_id, asyncio.Lock())
    async with lock:
        current = await db.get_movie(tv_id)
        if current and current.get("media_type") not in (None, "tv"):
            return None
        if current and not force:
            stamp = current.get("metadata_updated_at")
            if stamp:
                try:
                    updated = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                    if (datetime.now(timezone.utc) - updated).total_seconds() < TV_METADATA_TTL_DAYS * 86400:
                        return current
                except ValueError:
                    pass

        payload = await tmdb.get_tv_details_extended(tv_id)
        if not payload:
            return current if current and current.get("media_type") == "tv" else None
        next_episode = payload.get("next_episode_to_air") or {}
        await db.save_movie({
            "id": tv_id,
            "title": payload.get("name") or "Без названия",
            "year": (payload.get("first_air_date") or "")[:4],
            "rating_numeric": payload.get("vote_average", 0),
            "overview": payload.get("overview") or "",
            "poster_url": payload.get("poster_path") or "",
            "genres_array": [g.get("name") for g in payload.get("genres", []) if g.get("name")],
            "media_type": "tv",
            "actors": [a.get("name") for a in (payload.get("credits") or {}).get("cast", [])[:5] if a.get("name")],
            "directors": [d.get("name") for d in (payload.get("credits") or {}).get("crew", []) if d.get("job") == "Director"],
            "runtime_mins": (payload.get("episode_run_time") or [0])[0],
            "seasons": payload.get("number_of_seasons"),
            "number_of_episodes": payload.get("number_of_episodes"),
            "tv_status": payload.get("status"),
            "last_air_date": payload.get("last_air_date"),
            "next_episode": next_episode.get("air_date"),
            "metadata_updated_at": datetime.now(timezone.utc).isoformat(),
        })
        for season in payload.get("seasons") or []:
            season_number = season.get("season_number")
            if isinstance(season_number, int) and season_number > 0:
                await db.upsert_tv_season({
                    "tv_id": tv_id,
                    "season_number": season_number,
                    "name": season.get("name"),
                    "episode_count": season.get("episode_count") or 0,
                    "air_date": season.get("air_date"),
                    "poster_path": season.get("poster_path"),
                    "metadata_updated_at": datetime.now(timezone.utc).isoformat(),
                })
        return await db.get_movie(tv_id)


async def load_tv_season(tv_id: int, season_number: int, force: bool = False) -> list[dict]:
    existing = await db.get_tv_episodes(tv_id, season_number)
    if existing and not force:
        stamp = existing[0].get("metadata_updated_at")
        if stamp:
            try:
                updated = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - updated).days < SEASON_METADATA_TTL_DAYS:
                    return existing
            except ValueError:
                pass

    payload = await tmdb.get_tv_season_details(tv_id, season_number)
    if not payload:
        return existing
    await db.upsert_tv_season({
        "tv_id": tv_id,
        "season_number": season_number,
        "name": payload.get("name"),
        "episode_count": len(payload.get("episodes") or []),
        "air_date": payload.get("air_date"),
        "poster_path": payload.get("poster_path"),
        "metadata_updated_at": datetime.now(timezone.utc).isoformat(),
    })
    rows = []
    for episode in payload.get("episodes") or []:
        if episode.get("episode_number", 0) <= 0:
            continue
        row = {
            "tv_id": tv_id,
            "season_number": season_number,
            "episode_number": episode.get("episode_number"),
            "name": episode.get("name"),
            "overview": episode.get("overview"),
            "air_date": episode.get("air_date"),
            "runtime_mins": episode.get("runtime"),
            "still_path": episode.get("still_path"),
            "metadata_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        rows.append(row)
    await db.upsert_tv_episodes(rows)
    return await db.get_tv_episodes(tv_id, season_number)


async def get_tv_season_progress(user_id: int, tv_id: int, season_number: int) -> dict[str, Any] | None:
    episodes = await load_tv_season(tv_id, season_number)
    progress = await db.get_user_episode_progress(user_id, tv_id)
    watched = {(r["season_number"], r["episode_number"]) for r in progress}
    released = [e for e in episodes if _is_released(e.get("air_date"))]
    season = next((s for s in await db.get_tv_seasons(tv_id) if s["season_number"] == season_number), None)
    if season is None:
        return None
    return {
        **season,
        "available_episode_count": len(released),
        "watched_episode_count": sum((season_number, e["episode_number"]) in watched for e in released),
        "episodes": [{**e, "watched": (season_number, e["episode_number"]) in watched} for e in episodes],
    }


async def get_tv_progress(user_id: int, tv_id: int) -> dict[str, Any]:
    seasons = await db.get_tv_seasons(tv_id)
    cached_episodes = await db.get_tv_episodes_for_tv(tv_id)
    progress = await db.get_user_episode_progress(user_id, tv_id)
    watched = {(r["season_number"], r["episode_number"]) for r in progress}
    season_rows = []
    available_total = 0
    available_watched = 0
    next_episode = None
    for season in seasons:
        episodes = [e for e in cached_episodes if e["season_number"] == season["season_number"]]
        released = [e for e in episodes if _is_released(e.get("air_date"))]
        season_watched = [e for e in released if (season["season_number"], e["episode_number"]) in watched]
        available_total += len(released)
        available_watched += len(season_watched)
        if next_episode is None:
            next_episode = next_episode or choose_next_episode(
                [{**e, "season_number": season["season_number"]} for e in released], watched
            )
        known_total = season.get("episode_count") or 0
        season_rows.append({
            **season,
            "available_episode_count": len(released) if episodes else None,
            "watched_episode_count": len(season_watched),
            "episode_count": known_total,
            "loaded": bool(episodes),
            "episodes": [{**e, "watched": (season["season_number"], e["episode_number"]) in watched} for e in episodes],
        })
    metadata = await db.get_movie(tv_id) or {}
    status = metadata.get("tv_status") or ""
    user_media = await db.get_user_movie(user_id, tv_id)
    caught_up = available_total > 0 and available_watched == available_total and all(s["loaded"] for s in season_rows)
    state = compute_tv_state(user_media.status if user_media else None, available_watched, available_total, status)
    return {
        "seasons": season_rows,
        "watched_episodes": available_watched,
        "available_episodes": available_total,
        "known_episodes": sum(int(s.get("episode_count") or 0) for s in season_rows),
        "next_episode": next_episode,
        "caught_up": caught_up,
        "completed": caught_up and status in {"Ended", "Canceled", "Завершен"},
        "state": state,
        "tv_status": status,
        "next_air_date": metadata.get("next_episode"),
        "notification_enabled": await db.get_tv_notification_subscription(user_id, tv_id),
    }


async def set_episode_watched(user_id: int, tv_id: int, season_number: int, episode_number: int, watched: bool) -> dict[str, Any]:
    episodes = await load_tv_season(tv_id, season_number)
    episode = next((e for e in episodes if e.get("episode_number") == episode_number), None)
    if not episode or not _is_released(episode.get("air_date")):
        raise ValueError("episode_not_available")
    if watched:
        if not await db.get_user_movie(user_id, tv_id):
            await db.upsert_user_movie(user_id, tv_id, "watchlist", media_type="tv")
        await db.mark_episode_watched(user_id, tv_id, season_number, episode_number)
    else:
        await db.unmark_episode_watched(user_id, tv_id, season_number, episode_number)
    return await get_tv_progress(user_id, tv_id)


async def set_season_watched(user_id: int, tv_id: int, season_number: int, watched: bool) -> dict[str, Any]:
    episodes = await load_tv_season(tv_id, season_number)
    if watched and episodes and not await db.get_user_movie(user_id, tv_id):
        await db.upsert_user_movie(user_id, tv_id, "watchlist", media_type="tv")
    for episode in episodes:
        if _is_released(episode.get("air_date")):
            await (db.mark_episode_watched if watched else db.unmark_episode_watched)(
                user_id, tv_id, season_number, episode["episode_number"]
            )
    return await get_tv_progress(user_id, tv_id)
