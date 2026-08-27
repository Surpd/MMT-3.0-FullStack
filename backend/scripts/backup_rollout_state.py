"""Create a lossless application-level Supabase backup outside the repository.

The command is read-only. It uses SUPABASE_URL and the backend-only privileged
Supabase service key, then writes one JSON file per table.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from supabase_credentials import get_supabase_service_key


TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("users", ("id",)),
    ("movies", ("id",)),
    ("user_movies", ("user_id", "movie_id")),
    ("user_stats", ("user_id",)),
    ("tv_seasons", ("tv_id", "season_number")),
    ("tv_episodes", ("tv_id", "season_number", "episode_number")),
    ("user_episode_progress", ("user_id", "tv_id", "season_number", "episode_number")),
    ("tv_notification_subscriptions", ("user_id", "tv_id")),
    ("tv_notification_deliveries", ("user_id", "tv_id", "season_number", "episode_number")),
)
PAGE_SIZE = 500


def _client() -> Client:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    url = os.getenv("SUPABASE_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_URL is required")
    return create_client(url, get_supabase_service_key())


def _fetch_table(client: Client, table: str, order_columns: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = client.table(table).select("*")
        for column in order_columns:
            query = query.order(column)
        response = query.range(offset, offset + PAGE_SIZE - 1).execute()
        page = list(response.data or [])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def _write_json(path: Path, value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_backup(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    client = _client()
    manifest: dict[str, Any] = {
        "format": "mmt-application-backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": {},
        "notes": [
            "Application-level REST snapshot; not an atomic database transaction.",
            "ratings are stored in user_movies.rating; there is no separate ratings table in the captured schema.",
        ],
    }
    try:
        for table, order_columns in TABLES:
            rows = _fetch_table(client, table, order_columns)
            filename = f"{table}.json"
            digest = _write_json(output_dir / filename, rows)
            manifest["tables"][table] = {
                "file": filename,
                "rows": len(rows),
                "sha256": digest,
                "order_columns": list(order_columns),
            }
            print(f"backup table={table} rows={len(rows)}")
    except Exception:
        for path in output_dir.glob("*.json"):
            path.unlink(missing_ok=True)
        output_dir.rmdir()
        raise

    manifest_path = output_dir / "manifest.json"
    manifest["manifest_sha256"] = _write_json(manifest_path, manifest)
    return manifest


def verify_backup(output_dir: Path) -> dict[str, Any]:
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    verified = 0
    for table, info in manifest["tables"].items():
        path = output_dir / info["file"]
        rows = json.loads(path.read_text(encoding="utf-8"))
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if len(rows) != info["rows"] or actual_hash != info["sha256"]:
            raise RuntimeError(f"backup verification failed for {table}")
        verified += 1
    return {"tables": verified, "rows": sum(info["rows"] for info in manifest["tables"].values())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory outside the repository")
    args = parser.parse_args()
    manifest = create_backup(args.output)
    verification = verify_backup(args.output)
    print(f"backup_verified tables={verification['tables']} rows={verification['rows']}")
    print(f"backup_dir={args.output}")
    for table, info in manifest["tables"].items():
        print(f"sha256 table={table} hash={info['sha256']}")


if __name__ == "__main__":
    main()
