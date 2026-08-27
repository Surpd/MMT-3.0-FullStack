"""Seed an isolated Supabase project for authenticated local/E2E checks.

This script intentionally requires TEST_SUPABASE_URL/TEST_SUPABASE_KEY so it
cannot write to the application's ordinary Supabase target by accident.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv


MAX_TEST_USER_ID = 2_000_000_000
LIBRARY_SIZE = 25
CATALOG_SIZE = 40


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
    return _test_user_id(), url, key


async def bootstrap() -> None:
    user_id, url, key = _require_safe_test_target()
    from services.database import SupabaseDatabase

    db = SupabaseDatabase(url=url, key=key)
    await db.ensure_user(user_id, username="mmt_test_user", first_name="Test User")
    for index in range(CATALOG_SIZE):
        movie_id = 900001000 + index
        await db.save_movie(
            {
                "id": movie_id,
                "title": f"MMT Test Movie {index + 1:02d}",
                "media_type": "movie",
                "year": 2000 + index,
                "overview": f"Deterministic integration fixture movie number {index + 1} with enough text for quiz questions.",
                "poster_url": "/mmt-test-poster.jpg",
                "genres_array": ["Drama" if index % 2 == 0 else "Comedy"],
                "actors": [f"MMT Test Actor {index + 1:02d}"],
                "directors": [f"MMT Test Director {index + 1:02d}"],
                "tmdb_vote_count": 100,
            }
        )
        if index < LIBRARY_SIZE:
            await db.upsert_user_movie(
                user_id=user_id,
                movie_id=movie_id,
                status="liked",
                media_type="movie",
                rating=(index % 5) + 1 if index < 5 else None,
            )
    print(f"Seeded test user {user_id} with {LIBRARY_SIZE} liked titles")


if __name__ == "__main__":
    asyncio.run(bootstrap())
