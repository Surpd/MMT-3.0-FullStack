"""Run only the aiohttp API for local authenticated browser tests."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import bot, tmdb
from main import start_web_server


async def main() -> None:
    runner = await start_web_server()
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await tmdb.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
