"""Dry-run recovery of application rows from backup_rollout_state.py.

Recovery is additive/upsert-only and never deletes rows. It is intentionally
disabled by default; use --write --confirm-restore only after a failed rollout
has been diagnosed and the target schema has been verified.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from supabase_credentials import get_supabase_service_key


TABLE_ORDER = (
    "users",
    "movies",
    "user_movies",
    "user_stats",
    "tv_seasons",
    "tv_episodes",
    "user_episode_progress",
    "tv_notification_subscriptions",
    "tv_notification_deliveries",
)
CONFLICT_KEYS = {
    "users": "id",
    "movies": "id,media_type",
    "user_movies": "user_id,movie_id,media_type",
    "user_stats": "user_id",
    "tv_seasons": "tv_id,season_number",
    "tv_episodes": "tv_id,season_number,episode_number",
    "user_episode_progress": "user_id,tv_id,season_number,episode_number",
    "tv_notification_subscriptions": "user_id,tv_id",
    "tv_notification_deliveries": "user_id,tv_id,season_number,episode_number",
}
TV_TABLES = {"tv_seasons", "tv_notification_subscriptions", "tv_notification_deliveries"}


def _client() -> Client:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    url = os.getenv("SUPABASE_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_URL is required")
    return create_client(url, get_supabase_service_key())


def _load_rows(backup_dir: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    rows_by_table = {
        table: json.loads((backup_dir / info["file"]).read_text(encoding="utf-8"))
        for table, info in manifest["tables"].items()
    }
    return manifest, rows_by_table


def _post_migration_row(table: str, row: dict[str, Any], movie_types: dict[int, str]) -> dict[str, Any]:
    result = dict(row)
    if table == "movies":
        result["media_type"] = result.get("media_type") or "movie"
    elif table in TV_TABLES:
        result["media_type"] = "tv"
    elif table == "user_movies":
        result["media_type"] = result.get("media_type") or movie_types.get(int(result["movie_id"]), "movie")
    return result


def recover(backup_dir: Path, *, write: bool, confirm: bool) -> dict[str, int]:
    if write and not confirm:
        raise RuntimeError("--write requires --confirm-restore")
    manifest, raw_rows = _load_rows(backup_dir)
    movie_types = {
        int(row["id"]): row.get("media_type") or "movie"
        for row in raw_rows.get("movies", [])
        if row.get("id") is not None
    }
    rows_by_table = {
        table: [_post_migration_row(table, row, movie_types) for row in rows]
        for table, rows in raw_rows.items()
    }
    counts = {table: len(rows_by_table.get(table, [])) for table in TABLE_ORDER}
    print("recovery_mode=" + ("write" if write else "dry-run"))
    print("source_rows=" + str(sum(counts.values())))
    if not write:
        return counts

    client = _client()
    for table in TABLE_ORDER:
        rows = rows_by_table.get(table, [])
        for offset in range(0, len(rows), 100):
            client.table(table).upsert(
                rows[offset:offset + 100],
                on_conflict=CONFLICT_KEYS[table],
            ).execute()
        print(f"restored table={table} rows={len(rows)}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--confirm-restore", action="store_true")
    args = parser.parse_args()
    recover(args.backup, write=args.write, confirm=args.confirm_restore)


if __name__ == "__main__":
    main()
