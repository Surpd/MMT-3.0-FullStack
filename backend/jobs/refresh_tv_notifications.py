"""One-shot notification job. Run from Render Cron, not from the web process."""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from html import escape
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import bot, db, WEBAPP_URL
from services.tv_service import load_tv_season, refresh_tv_metadata

logger = logging.getLogger(__name__)


async def run() -> None:
    metadata_cache: dict[int, dict] = {}
    episode_cache: dict[tuple[int, int], list[dict]] = {}
    for subscription in await db.get_tv_notification_subscriptions():
        user_id = int(subscription["user_id"])
        tv_id = int(subscription["tv_id"])
        try:
            if tv_id not in metadata_cache:
                metadata_cache[tv_id] = await refresh_tv_metadata(tv_id, force=True) or {}
            metadata = metadata_cache[tv_id]
            for season_number in range(1, int((metadata or {}).get("seasons") or 0) + 1):
                cache_key = (tv_id, season_number)
                if cache_key not in episode_cache:
                    episode_cache[cache_key] = await load_tv_season(tv_id, season_number, force=True)
                episodes = episode_cache[cache_key]
                for episode in episodes:
                    air_date = episode.get("air_date")
                    if not air_date or air_date > date.today().isoformat():
                        continue
                    if await db.has_tv_notification_delivery(user_id, tv_id, season_number, episode["episode_number"]):
                        continue
                    title = escape(str((metadata or {}).get("title") or "Сериал"))
                    episode_name = escape(str(episode.get("name") or ""))
                    await bot.send_message(
                        user_id,
                        f"📺 Новая серия: {title} · S{season_number:02d}E{episode['episode_number']:02d}\n{episode_name}",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="Открыть Mini App", web_app=WebAppInfo(url=WEBAPP_URL))
                        ]]),
                    )
                    await db.mark_tv_notification_delivery(user_id, tv_id, season_number, episode["episode_number"])
        except Exception:
            logger.exception("TV notification processing failed for user=%s tv=%s", user_id, tv_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
