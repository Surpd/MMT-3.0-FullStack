from __future__ import annotations

import html
from typing import Any


def build_progress_bar(watched: int, available: int, width: int = 10) -> str:
    watched = max(0, int(watched or 0))
    available = max(0, int(available or 0))
    width = max(1, int(width))
    if available <= 0:
        return "░" * width
    filled = min(width, int((watched / available) * width))
    return "█" * filled + "░" * (width - filled)


async def get_tracked_series_page(db: Any, user_id: int, page: int, page_size: int = 5) -> tuple[list[dict], int]:
    from services.tv_service import get_tv_progress_summaries

    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 10))
    subscriptions = await db.get_user_tv_notification_subscriptions(user_id)
    tv_ids = list(dict.fromkeys(int(row["tv_id"]) for row in subscriptions if row.get("tv_id") is not None))
    total = len(tv_ids)
    if not tv_ids:
        return [], 0

    metadata_rows = await db.get_movies_by_ids(tv_ids)
    metadata_by_tv_id = {
        int(row["id"]): row
        for row in metadata_rows
        if row.get("id") is not None and (row.get("media_type") or "movie") == "tv"
    }
    summaries = await get_tv_progress_summaries(
        user_id,
        tv_ids,
        ensure_metadata=False,
        metadata_by_tv_id=metadata_by_tv_id,
    )
    start = (page - 1) * page_size
    items = []
    for tv_id in tv_ids[start:start + page_size]:
        summary = dict(summaries.get(tv_id) or {})
        summary["tv_id"] = tv_id
        summary["title"] = summary.get("title") or (metadata_by_tv_id.get(tv_id) or {}).get("title") or f"Сериал {tv_id}"
        items.append(summary)
    return items, total


def render_tracked_series_page(items: list[dict], page: int, total: int, page_size: int = 5) -> str:
    if not items:
        return "🔔 <b>Отслеживаемые сериалы</b>\n\nПока нет сериалов с включёнными уведомлениями."
    lines = ["🔔 <b>Отслеживаемые сериалы</b>", ""]
    for item in items:
        title = html.escape(str(item.get("title") or "Без названия"))
        watched = int(item.get("watched_episodes") or 0)
        available = int(item.get("available_episodes") or 0)
        progress = f"{watched} из {available}" if available else "прогресс загружается"
        lines.append(f"📺 <b>{title}</b>\n{build_progress_bar(watched, available)} {progress}")
        next_episode = item.get("next_episode") or {}
        if next_episode:
            season = int(next_episode.get("season_number") or 0)
            episode = int(next_episode.get("episode_number") or 0)
            episode_title = html.escape(str(next_episode.get("name") or "Следующая серия"))
            lines.append(f"▶️ S{season:02d}E{episode:02d} · {episode_title}")
        lines.append("")
    return "\n".join(lines).strip()[:4000]
