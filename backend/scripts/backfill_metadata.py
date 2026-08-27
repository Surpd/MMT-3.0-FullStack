"""Idempotent TMDB metadata backfill. Run --dry-run before any writes."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("metadata_backfill")
STALE_AFTER = timedelta(days=30)
CONCURRENCY = 4
DEFAULT_RPS = 4


def _needs_refresh(row: dict[str, Any], force: bool) -> bool:
    required = (
        row.get("keywords"), row.get("directors"),
        row.get("production_countries") or row.get("origin_country"),
        row.get("tmdb_vote_count"), row.get("genres_array"),
    )
    if force or any(value in (None, "", []) for value in required):
        return True
    stamp = row.get("metadata_updated_at")
    if not stamp:
        return True
    try:
        updated = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) - updated >= STALE_AFTER


def _metadata_payload(row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    media_type = row.get("media_type") or ("tv" if payload.get("name") else "movie")
    credits = payload.get("credits") or {}
    result: dict[str, Any] = {
        "metadata_updated_at": datetime.now(timezone.utc).isoformat(),
        "media_type": media_type,
        "genres_array": [g.get("name") for g in payload.get("genres") or [] if g.get("name")],
        "rating_numeric": payload.get("vote_average"),
        "tmdb_vote_count": payload.get("vote_count"),
        "keywords": [item.get("name") for item in ((payload.get("keywords") or {}).get("keywords") or (payload.get("keywords") or {}).get("results") or []) if item.get("name")],
        "overview": payload.get("overview") or row.get("overview"),
        "poster_url": payload.get("poster_path") or row.get("poster_url"),
        "backdrop_url": payload.get("backdrop_path"),
        "original_language": payload.get("original_language"),
        "actors": [a.get("name") for a in (credits.get("cast") or [])[:10] if a.get("name")],
        "directors": [c.get("name") for c in (credits.get("crew") or []) if c.get("job") in {"Director", "Creator"} and c.get("name")],
        "production_companies": [c.get("name") for c in payload.get("production_companies") or [] if c.get("name")],
    }
    if media_type == "tv":
        result.update({"origin_country": [c for c in payload.get("origin_country") or [] if c], "original_title": payload.get("original_name"), "year": (payload.get("first_air_date") or row.get("year") or "")[:4], "tv_status": payload.get("status") or row.get("tv_status"), "seasons": payload.get("number_of_seasons"), "number_of_episodes": payload.get("number_of_episodes"), "last_air_date": payload.get("last_air_date")})
    else:
        result.update({"production_countries": [c.get("iso_3166_1") for c in payload.get("production_countries") or [] if c.get("iso_3166_1")], "original_title": payload.get("original_title"), "year": (payload.get("release_date") or row.get("year") or "")[:4], "runtime_mins": payload.get("runtime") or row.get("runtime_mins")})
    return {key: value for key, value in result.items() if value is not None}


def _has_value(value: Any) -> bool:
    return value not in (None, "", [])


def _merge_missing_metadata(existing: dict[str, Any], incoming: dict[str, Any], force: bool = False) -> dict[str, Any]:
    """Keep non-empty local values; make a rerun safe after partial failures."""
    merged = {}
    for key, value in incoming.items():
        if key == "metadata_updated_at":
            merged[key] = value
        elif _has_value(value) and (force or not _has_value(existing.get(key))):
            merged[key] = value
    return merged


async def _fetch(row: dict[str, Any], semaphore: asyncio.Semaphore, limiter: "RateLimiter", tmdb_client: Any) -> tuple[str, dict[str, Any] | None]:
    async with semaphore:
        for attempt in range(3):
            try:
                await limiter.wait()
                payload = await (tmdb_client.get_tv_details_extended(row["id"]) if row.get("media_type") == "tv" else tmdb_client.get_movie_details_extended(row["id"]))
                return ("updated", _metadata_payload(row, payload)) if payload else ("not_found", None)
            except Exception as exc:
                if attempt == 2:
                    logger.warning("failed id=%s: %s", row.get("id"), exc)
                    return "failed", None
                await asyncio.sleep(2 ** attempt)
    return "failed", None


class RateLimiter:
    def __init__(self, requests_per_second: float):
        self.interval = 1.0 / max(0.1, requests_per_second)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = asyncio.get_running_loop().time()
            delay = self.interval - (now - self._last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = asyncio.get_running_loop().time()


async def run(dry_run: bool = True, force: bool = False, limit: int | None = None,
              offset: int = 0, rps: float = DEFAULT_RPS) -> dict[str, int]:
    from config import db, tmdb

    rows: list[dict[str, Any]] = []
    page_offset = 0
    while True:
        page = await db.get_movies_for_backfill(offset=page_offset, limit=100)
        rows.extend(page)
        if len(page) < 100:
            break
        page_offset += len(page)
    candidates = [row for row in rows if _needs_refresh(row, force)]
    candidates = candidates[offset:]
    if limit:
        candidates = candidates[:limit]
    print(
        f"dry_run={dry_run} candidates={len(candidates)} "
        f"movies={sum(r.get('media_type') == 'movie' for r in candidates)} "
        f"tv={sum(r.get('media_type') == 'tv' for r in candidates)} "
        f"estimated_tmdb_requests={len(candidates)} max_attempts={len(candidates) * 3}"
    )
    if dry_run:
        return {"candidates": len(candidates), "estimated_tmdb_requests": len(candidates)}
    semaphore = asyncio.Semaphore(CONCURRENCY)
    limiter = RateLimiter(rps)
    results = []
    for index in range(0, len(candidates), CONCURRENCY):
        batch = candidates[index:index + CONCURRENCY]
        results.extend(await asyncio.gather(*(_fetch(row, semaphore, limiter, tmdb) for row in batch)))
        logger.info("progress processed=%s/%s", min(index + CONCURRENCY, len(candidates)), len(candidates))
    counts = {key: sum(status == key for status, _ in results) for key in ("updated", "not_found", "failed")}
    print(f"planned_updates={counts['updated']} not_found={counts['not_found']} failed={counts['failed']}")
    updated = 0
    for row, (status, payload) in zip(candidates, results):
        if status == "updated" and payload:
            update = _merge_missing_metadata(row, payload, force=force)
            if update:
                await db.update_movie_metadata(row["id"], row.get("media_type") or "movie", update)
            updated += 1
    print(f"processed={len(candidates)} updated={updated} skipped={len(rows)-len(candidates)} not_found={counts['not_found']} failed={counts['failed']}")
    return {"processed": len(candidates), "updated": updated,
            "not_found": counts["not_found"], "failed": counts["failed"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--write", action="store_true", help="apply updates; dry-run is the default")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--rps", type=float, default=DEFAULT_RPS)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(not args.write, args.force, args.limit, args.offset, args.rps))
