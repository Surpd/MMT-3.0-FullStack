from __future__ import annotations

import asyncio
import logging
from datetime import date
from html import escape
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from services.tv_service import load_tv_season, refresh_tv_metadata

logger = logging.getLogger(__name__)
_run_lock = asyncio.Lock()


async def run_tv_notification_scan(db, bot: Bot, webapp_url: str) -> dict[str, int | bool]:
    """Process only enabled subscriptions and return a technical summary."""
    if _run_lock.locked():
        return {"ok": False, "busy": True, "subscriptions_checked": 0, "shows_checked": 0, "notifications_sent": 0, "failures": 0}

    async with _run_lock:
        subscriptions = await db.get_tv_notification_subscriptions()
        metadata_cache: dict[int, dict[str, Any]] = {}
        episode_cache: dict[tuple[int, int], list[dict[str, Any]]] = {}
        shows_checked: set[int] = set()
        notifications_sent = 0
        failures = 0

        for subscription in subscriptions:
            user_id = int(subscription["user_id"])
            tv_id = int(subscription["tv_id"])
            shows_checked.add(tv_id)
            try:
                if tv_id not in metadata_cache:
                    metadata_cache[tv_id] = await refresh_tv_metadata(tv_id, force=True) or {}
                metadata = metadata_cache[tv_id]
                for season_number in range(1, int(metadata.get("seasons") or 0) + 1):
                    cache_key = (tv_id, season_number)
                    if cache_key not in episode_cache:
                        episode_cache[cache_key] = await load_tv_season(tv_id, season_number, force=True)
                    for episode in episode_cache[cache_key]:
                        air_date = episode.get("air_date")
                        if not air_date or air_date > date.today().isoformat():
                            continue
                        episode_number = int(episode["episode_number"])
                        if await db.has_tv_notification_delivery(user_id, tv_id, season_number, episode_number):
                            continue
                        title = escape(str(metadata.get("title") or "Сериал"))
                        episode_name = escape(str(episode.get("name") or ""))
                        await bot.send_message(
                            user_id,
                            f"📺 Новая серия: {title} · S{season_number:02d}E{episode_number:02d}\n{episode_name}",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(text="Открыть Mini App", web_app=WebAppInfo(url=webapp_url))
                            ]]),
                        )
                        await db.mark_tv_notification_delivery(user_id, tv_id, season_number, episode_number)
                        notifications_sent += 1
            except Exception:
                failures += 1
                logger.exception("TV notification processing failed for user=%s tv=%s", user_id, tv_id)

        return {
            "ok": failures == 0,
            "busy": False,
            "subscriptions_checked": len(subscriptions),
            "shows_checked": len(shows_checked),
            "notifications_sent": notifications_sent,
            "failures": failures,
        }
