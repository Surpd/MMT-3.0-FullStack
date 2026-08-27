"""Reset the reserved synthetic user for authenticated local/E2E checks."""

from __future__ import annotations

import asyncio
import socket
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
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
    if os.getenv("TEST_SUPABASE_URL", "").strip() or os.getenv("TEST_SUPABASE_KEY", "").strip():
        raise RuntimeError(
            "TEST_SUPABASE_* is no longer supported; use SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY with ALLOW_PRODUCTION_TEST_USER=true"
        )
    allow_primary = os.getenv("ALLOW_PRODUCTION_TEST_USER", "false").strip().lower() == "true"
    ordinary_url = os.getenv("SUPABASE_URL", "").strip()
    if not allow_primary:
        raise RuntimeError("Set ALLOW_PRODUCTION_TEST_USER=true for the reserved local test user")
    if not ordinary_url:
        raise RuntimeError("SUPABASE_URL is required with ALLOW_PRODUCTION_TEST_USER=true")
    from supabase_credentials import get_supabase_service_key

    return _test_user_id(), ordinary_url, get_supabase_service_key()


async def _check_read_only_connectivity(url: str, key: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise RuntimeError("SUPABASE_URL must be an https URL with a valid hostname")
    hostname = parsed.hostname
    port = parsed.port or 443
    print(f"Supabase URL parsed; hostname {hostname}", flush=True)
    try:
        await asyncio.to_thread(socket.getaddrinfo, hostname, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError) as exc:
        raise RuntimeError(f"Supabase DNS resolution failed for hostname {hostname}") from exc
    print(f"Supabase DNS resolution OK for hostname {hostname}", flush=True)

    endpoint = f"{url.rstrip('/')}/rest/v1/movies?select=id&limit=1"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(endpoint, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Supabase read-only connectivity failed for hostname {hostname}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"Supabase read-only connectivity returned HTTP {response.status_code}")
    print(f"Supabase read-only connectivity OK for hostname {hostname}", flush=True)
    return hostname


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
    await _check_read_only_connectivity(url, key)
    from services.database import SupabaseDatabase

    db = SupabaseDatabase(url=url, key=key)
    await _assert_reserved_identity(db, user_id)
    catalog = await _load_catalog(db)
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
    try:
        asyncio.run(bootstrap())
    except RuntimeError as exc:
        print(f"Test target preflight failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
