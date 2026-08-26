"""One-shot notification job. Run from Render Cron, not from the web process."""
from __future__ import annotations

import asyncio
from config import bot, db, WEBAPP_URL
from services.tv_notification_service import run_tv_notification_scan


async def run() -> None:
    await run_tv_notification_scan(db, bot, WEBAPP_URL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
