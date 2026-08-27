"""Deterministically bootstrap existing taste profiles from current library state.

Dry-run is the default. Use --write only from an approved migration runbook after
the user_taste_profiles migration has been verified. This never changes user_movies.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("taste_bootstrap")


def group_rows(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows or []:
        if row.get("user_id") is not None:
            grouped[int(row["user_id"])].append(row)
    return dict(grouped)


def missing_metadata(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Count unique catalog rows missing feature groups used by taste scoring."""
    unique: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows or []:
        movie = row.get("movies") or {}
        if row.get("movie_id") is None:
            continue
        key = (int(row["movie_id"]), row.get("media_type") or movie.get("media_type") or "movie")
        unique.setdefault(key, movie)
    fields = ("genres_array", "keywords", "directors", "countries", "tmdb_vote_count")
    result = {field: 0 for field in fields}
    result["titles"] = len(unique)
    for movie in unique.values():
        if not movie.get("genres_array") and not movie.get("genres") and not movie.get("genre_ids"):
            result["genres_array"] += 1
        for field in fields[1:]:
            if field == "countries":
                present = movie.get("production_countries") or movie.get("origin_country")
            else:
                present = movie.get(field)
            if present in (None, "", []):
                result[field] += 1
    return result


def summarize(user_ids: list[int], rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(row.get("status") for row in rows or [])
    return {
        "users": len(user_ids),
        "profiles": len(user_ids),
        "liked": counts.get("liked", 0),
        "watchlist": counts.get("watchlist", 0),
        "archive": counts.get("archive", 0),
        "missing_metadata": missing_metadata(rows),
    }


async def run(*, dry_run: bool = True, limit: int | None = None, offset: int = 0) -> dict[str, Any]:
    from config import db, recommendation_service, session_cache

    user_ids = (await db.get_user_ids())[offset:]
    if limit is not None:
        user_ids = user_ids[:limit]
    rows = await db.get_all_user_recommendation_rows()
    grouped = group_rows(rows)
    report = summarize(user_ids, [row for user_id in user_ids for row in grouped.get(user_id, [])])
    missing = report["missing_metadata"]
    print(
        "users={users} profiles={profiles} liked={liked} watchlist={watchlist} archive={archive} "
        "titles={titles} missing_keywords={keywords} missing_directors={directors} "
        "missing_countries={countries} missing_vote_count={votes} missing_genres={genres}".format(
            users=report["users"], profiles=report["profiles"], liked=report["liked"],
            watchlist=report["watchlist"], archive=report["archive"], titles=missing["titles"],
            keywords=missing["keywords"], directors=missing["directors"],
            countries=missing["countries"],
            votes=missing["tmdb_vote_count"], genres=missing["genres_array"],
        )
    )
    if dry_run:
        return report

    processed = failures = 0
    for user_id in user_ids:
        try:
            await recommendation_service.bootstrap_taste_profile(user_id, grouped.get(user_id, []))
            await recommendation_service.invalidate_user_cache(user_id)
            if session_cache and hasattr(session_cache, "delete"):
                await session_cache.delete(f"session_{user_id}")
            processed += 1
        except Exception:
            failures += 1
            logger.exception("bootstrap failed user_id=%s", user_id)
        if processed + failures == 1 or (processed + failures) % 25 == 0:
            logger.info("progress processed=%s/%s failures=%s", processed + failures, len(user_ids), failures)
    print(f"write_complete processed={processed} failures={failures}")
    report.update({"processed": processed, "failures": failures})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="persist profiles; dry-run is the default")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(dry_run=not args.write, limit=args.limit, offset=args.offset))
