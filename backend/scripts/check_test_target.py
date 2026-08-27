"""Read-only preflight for the reserved local E2E Supabase target."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.bootstrap_test_user import _check_read_only_connectivity, _require_safe_test_target


async def main() -> None:
    user_id, url, key = _require_safe_test_target()
    hostname = await _check_read_only_connectivity(url, key)
    print(f"Test user {user_id}; target hostname {hostname}; no writes performed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as exc:
        print(f"Test target preflight failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
