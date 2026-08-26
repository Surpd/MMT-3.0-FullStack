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
from config import db, tmdb

logger = logging.getLogger("metadata_backfill")
STALE_AFTER = timedelta(days=30)
CONCURRENCY = 4


def _needs_refresh(row: dict[str, Any], force: bool) -> bool:
    if force or not (row.get("production_countries") or row.get("origin_country")):
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


async def _fetch(row: dict[str, Any], semaphore: asyncio.Semaphore) -> tuple[str, dict[str, Any] | None]:
    async with semaphore:
        for attempt in range(3):
            try:
                payload = await (tmdb.get_tv_details_extended(row["id"]) if row.get("media_type") == "tv" else tmdb.get_movie_details_extended(row["id"]))
                return ("updated", _metadata_payload(row, payload)) if payload else ("not_found", None)
            except Exception as exc:
                if attempt == 2:
                    logger.warning("failed id=%s: %s", row.get("id"), exc)
                    return "failed", None
                await asyncio.sleep(2 ** attempt)
    return "failed", None


async def run(dry_run: bool, force: bool, limit: int | None) -> None:
    response = await db._execute(db._client.table("movies").select("*"))
    rows = response.data or []
    candidates = [row for row in rows if _needs_refresh(row, force)]
    if limit:
        candidates = candidates[:limit]
    print(f"dry_run={dry_run} candidates={len(candidates)} movies={sum(r.get('media_type') == 'movie' for r in candidates)} tv={sum(r.get('media_type') == 'tv' for r in candidates)}")
    semaphore = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(_fetch(row, semaphore) for row in candidates))
    counts = {key: sum(status == key for status, _ in results) for key in ("updated", "not_found", "failed")}
    print(f"planned_updates={counts['updated']} not_found={counts['not_found']} failed={counts['failed']}")
    if dry_run:
        for row, (status, payload) in list(zip(candidates, results))[:5]:
            print(f"example id={row['id']} status={status} fields={sorted(payload) if payload else []}")
        return
    updated = 0
    for row, (status, payload) in zip(candidates, results):
        if status == "updated" and payload:
            await db._execute(db._client.table("movies").update(payload).eq("id", row["id"]))
            updated += 1
    print(f"processed={len(candidates)} updated={updated} skipped={len(rows)-len(candidates)} not_found={counts['not_found']} failed={counts['failed']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args.dry_run, args.force, args.limit))
