"""Seed an isolated Supabase project for authenticated local/E2E checks.

This script intentionally requires TEST_SUPABASE_URL/TEST_SUPABASE_KEY so it
cannot write to the application's ordinary Supabase target by accident.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

MAX_TEST_USER_ID = 2_000_000_000
LIBRARY_SIZE = 25
CATALOG_SIZE = 40
CATALOG_ID_START = 900001000


def _test_user_id() -> int:
    raw = os.getenv("TEST_USER_ID", "900000001").strip()
    if not raw.isdecimal() or int(raw) <= 0 or int(raw) > MAX_TEST_USER_ID:
        raise RuntimeError("TEST_USER_ID must be a positive integer <= 2000000000")
    return int(raw)


def _require_safe_test_target() -> tuple[int, str, str]:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    if os.getenv("TEST_MODE", "").strip().lower() != "true":
        raise RuntimeError("Set TEST_MODE=true before seeding test data")
    if os.getenv("RUNTIME_ENV", "development").strip().lower() in {"production", "staging"}:
        raise RuntimeError("Test data bootstrap is disabled in production-like runtime")
    url = os.getenv("TEST_SUPABASE_URL", "").strip()
    key = os.getenv("TEST_SUPABASE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("TEST_SUPABASE_URL and TEST_SUPABASE_KEY are required")
    if url == os.getenv("SUPABASE_URL", "").strip():
        raise RuntimeError("TEST_SUPABASE_URL must differ from SUPABASE_URL")
    return _test_user_id(), url, key


async def _execute(query: Any) -> Any:
    return await asyncio.to_thread(query.execute)


async def _reset_user(db: Any, user_id: int) -> None:
    await _execute(db._client.table("user_movies").delete().eq("user_id", user_id))
    await _execute(
        db._client.table("user_taste_profiles").delete().eq("user_id", user_id)
    )
    await _execute(
        db._client.table("user_stats")
        .update(
            {
                "points": 0,
                "quiz_total": 0,
                "quiz_correct": 0,
                "current_streak": 0,
                "best_streak": 0,
            }
        )
        .eq("user_id", user_id)
    )


async def bootstrap() -> None:
    user_id, url, key = _require_safe_test_target()
    from services.database import SupabaseDatabase

    db = SupabaseDatabase(url=url, key=key)
    await db._crud.ensure_user(user_id)
    await db.ensure_user(user_id, username="mmt_test_user", first_name="Test User")
    await _reset_user(db, user_id)
    for index in range(CATALOG_SIZE):
        movie_id = CATALOG_ID_START + index
        media_type = "tv" if index % 3 == 0 else "movie"
        await db.save_movie(
            {
                "id": movie_id,
                "title": f"MMT Test {'Series' if media_type == 'tv' else 'Movie'} {index + 1:02d}",
                "media_type": media_type,
                "year": 2000 + index,
                "overview": f"Deterministic integration fixture title number {index + 1} with enough text for quiz questions and profile metadata.",
                "poster_url": "/mmt-test-poster.jpg",
                "genres_array": ["Drama" if index % 2 == 0 else "Comedy"],
                "actors": [f"MMT Test Actor {index + 1:02d}"],
                "directors": [f"MMT Test Director {index + 1:02d}"],
                "tmdb_vote_count": 100,
                "seasons": 2 if media_type == "tv" else None,
                "number_of_episodes": 16 if media_type == "tv" else None,
                "tv_status": "Ended" if media_type == "tv" else None,
            }
        )
        if index < LIBRARY_SIZE:
            await db.upsert_user_movie(
                user_id=user_id,
                movie_id=movie_id,
                status="liked",
                media_type=media_type,
                rating=(index % 5) + 1 if index < 5 else None,
            )
    print(f"Reset and seeded test user {user_id} with {LIBRARY_SIZE} liked titles")


if __name__ == "__main__":
    asyncio.run(bootstrap())
