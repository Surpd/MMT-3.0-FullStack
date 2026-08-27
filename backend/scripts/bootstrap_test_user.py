"""Reset the reserved synthetic user for authenticated local/E2E checks."""

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
RESERVED_TEST_USER_ID = 900000001
LIBRARY_SIZE = 25
TEST_USERNAME = "mmt_test_user"
TEST_FIRST_NAME = "Test User"


def _test_user_id() -> int:
    raw = os.getenv("TEST_USER_ID", "900000001").strip()
    if not raw.isdecimal() or int(raw) <= 0 or int(raw) > MAX_TEST_USER_ID:
        raise RuntimeError("TEST_USER_ID must be a positive integer <= 2000000000")
    user_id = int(raw)
    if user_id != RESERVED_TEST_USER_ID:
        raise RuntimeError(f"TEST_USER_ID must remain the reserved synthetic ID {RESERVED_TEST_USER_ID}")
    return user_id


def _require_safe_test_target() -> tuple[int, str, str]:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    if os.getenv("TEST_MODE", "").strip().lower() != "true":
        raise RuntimeError("Set TEST_MODE=true before seeding test data")
    runtime = os.getenv("RUNTIME_ENV", "development").strip().lower()
    if runtime in {"production", "staging"}:
        raise RuntimeError("Test data bootstrap is disabled in production-like runtime")
    url = os.getenv("TEST_SUPABASE_URL", "").strip()
    key = os.getenv("TEST_SUPABASE_KEY", "").strip()
    allow_primary = os.getenv("ALLOW_PRODUCTION_TEST_USER", "false").strip().lower() == "true"
    if bool(url) != bool(key):
        raise RuntimeError("TEST_SUPABASE_URL and TEST_SUPABASE_KEY must be provided together")
    ordinary_url = os.getenv("SUPABASE_URL", "").strip()
    ordinary_key = os.getenv("SUPABASE_KEY", "").strip()
    if url and url == ordinary_url and not allow_primary:
        raise RuntimeError("TEST_SUPABASE_URL must differ from SUPABASE_URL")
    if not url:
        if not allow_primary:
            raise RuntimeError(
                "TEST_SUPABASE_URL and TEST_SUPABASE_KEY are required; set ALLOW_PRODUCTION_TEST_USER=true for the reserved local test user"
            )
        url, key = ordinary_url, ordinary_key
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required with ALLOW_PRODUCTION_TEST_USER=true")
    return _test_user_id(), url, key


async def _execute(query: Any) -> Any:
    return await asyncio.to_thread(query.execute)


async def _reset_user(db: Any, user_id: int) -> None:
    for table in (
        "user_movies",
        "user_taste_profiles",
        "user_episode_progress",
        "tv_notification_subscriptions",
        "tv_notification_deliveries",
    ):
        await _execute(db._client.table(table).delete().eq("user_id", user_id))
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


async def _assert_reserved_identity(db: Any, user_id: int) -> None:
    user_response = await _execute(
        db._client.table("users").select("id, username, first_name").eq("id", user_id).limit(1)
    )
    user_rows = user_response.data if user_response and getattr(user_response, "data", None) else []
    if user_rows:
        user = user_rows[0]
        if user.get("username") != TEST_USERNAME or user.get("first_name") != TEST_FIRST_NAME:
            raise RuntimeError("Reserved TEST_USER_ID already belongs to a non-synthetic users row")
        return

    profile_response = await _execute(
        db._client.table("profiles").select("id").eq("id", user_id).limit(1)
    )
    profile_rows = profile_response.data if profile_response and getattr(profile_response, "data", None) else []
    if profile_rows:
        raise RuntimeError("Reserved TEST_USER_ID already has an unverified profiles row")


async def _load_catalog(db: Any) -> list[dict[str, Any]]:
    response = await _execute(db._client.table("movies").select("*").order("id").limit(500))
    rows = response.data if response and getattr(response, "data", None) else []
    movies = [row for row in rows if row.get("media_type", "movie") == "movie" and row.get("title")]
    series = [row for row in rows if row.get("media_type") == "tv" and row.get("title")]
    if not movies or not series:
        raise RuntimeError("Test target needs existing movie and TV catalog rows; no catalog writes are performed")

    selected = movies[:13] + series[:12]
    if len(selected) < LIBRARY_SIZE:
        selected_keys = {(row.get("id"), row.get("media_type")) for row in selected}
        for row in rows:
            key = (row.get("id"), row.get("media_type"))
            if row.get("title") and key not in selected_keys:
                selected.append(row)
                selected_keys.add(key)
            if len(selected) == LIBRARY_SIZE:
                break
    if len(selected) < LIBRARY_SIZE:
        raise RuntimeError(f"Test target has only {len(selected)} usable catalog rows; need {LIBRARY_SIZE}")
    return selected


async def bootstrap() -> None:
    user_id, url, key = _require_safe_test_target()
    from services.database import SupabaseDatabase

    db = SupabaseDatabase(url=url, key=key)
    await _assert_reserved_identity(db, user_id)
    catalog = await _load_catalog(db)
    await db._crud.ensure_user(user_id)
    await db.ensure_user(user_id, username=TEST_USERNAME, first_name=TEST_FIRST_NAME)
    await _reset_user(db, user_id)
    for index, row in enumerate(catalog[:LIBRARY_SIZE]):
        await db.upsert_user_movie(
            user_id=user_id,
            movie_id=int(row["id"]),
            status="liked",
            media_type=row.get("media_type") or "movie",
            rating=(index % 5) + 1 if index < 5 else None,
        )
    print(f"Reset and seeded test user {user_id} with {LIBRARY_SIZE} liked titles")


if __name__ == "__main__":
    asyncio.run(bootstrap())
