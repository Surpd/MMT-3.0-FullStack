"""One-shot notification job. Run from Render Cron, not from the web process."""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from config import bot, db
from services.tv_service import load_tv_season, refresh_tv_metadata

logger = logging.getLogger(__name__)


async def run() -> None:
    for subscription in await db.get_tv_notification_subscriptions():
        user_id = int(subscription["user_id"])
        tv_id = int(subscription["tv_id"])
        try:
            metadata = await refresh_tv_metadata(tv_id, force=True)
            for season_number in range(1, int((metadata or {}).get("seasons") or 0) + 1):
                episodes = await load_tv_season(tv_id, season_number, force=True)
                for episode in episodes:
                    air_date = episode.get("air_date")
                    if not air_date or air_date > date.today().isoformat():
                        continue
                    if await db.has_tv_notification_delivery(user_id, tv_id, season_number, episode["episode_number"]):
                        continue
                    await bot.send_message(user_id, f"📺 Вышла новая серия: {(metadata or {}).get('title', 'Сериал')} · S{season_number:02d}E{episode['episode_number']:02d}\n{episode.get('name') or ''}")
                    await db.mark_tv_notification_delivery(user_id, tv_id, season_number, episode["episode_number"])
        except Exception:
            logger.exception("TV notification processing failed for user=%s tv=%s", user_id, tv_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
