"""Canonical user-title state transitions shared by web and Telegram entry points."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

async def apply_media_state(
    db: Any,
    recommendation_service: Any,
    user_id: int,
    movie_id: int,
    media_type: str,
    status: str,
    *,
    rating: int | None = None,
    action_id: str | None = None,
) -> dict[str, Any]:
    """Persist one canonical state change and update the derived taste snapshot.

    ``action_id`` protects retries from re-applying EMA.  A repeated state
    transition without an action id is also a no-op: it is a state write, not a
    new positive interaction.
    """
    canonical_status = {
        "liked": "liked", "watched": "liked", "watchlist": "watchlist",
        "archive": "archive", "disliked": "archive", "skip": "archive", "none": "none",
    }.get(status)
    if canonical_status is None:
        raise ValueError("invalid_media_status")
    status = canonical_status
    current = await db.get_user_movie(user_id, movie_id, media_type)
    current_action_id = getattr(current, "action_id", None) if current else None
    if action_id and current_action_id == action_id:
        return {"status": getattr(current, "status", status), "duplicate": True}
    if current and not action_id and status == getattr(current, "status", None) and rating is None:
        return {"status": getattr(current, "status", status), "duplicate": True}

    await db.upsert_user_movie(
        user_id=user_id,
        movie_id=movie_id,
        status=status,
        media_type=media_type,
        rating=rating,
        action_id=action_id,
    )

    try:
        if status in {"liked", "watchlist", "archive"}:
            if (current and status in {"liked", "watchlist"}
                    and getattr(current, "status", None) in {"liked", "watchlist"}
                    and getattr(current, "status", None) != status):
                # A status transition changes the strength of the existing
                # relation; rebuild so the title is not counted twice.
                await recommendation_service.rebuild_taste_profile(user_id)
            else:
                await recommendation_service.update_taste_profile(user_id, movie_id, media_type, status)
        elif status == "none":
            await recommendation_service.rebuild_taste_profile(user_id)
    except Exception as exc:
        # The source-of-truth state must not be lost if the derived snapshot
        # is unavailable during a migration or a transient DB failure.
        logger.exception("Taste update failed after state write: %s", exc)

    if hasattr(recommendation_service, "invalidate_user_cache"):
        await recommendation_service.invalidate_user_cache(user_id)
    return {"status": status, "duplicate": False}


async def apply_rating(db: Any, recommendation_service: Any, user_id: int, movie_id: int,
                       media_type: str, rating: int) -> None:
    current = await db.get_user_movie(user_id, movie_id, media_type)
    await db.upsert_user_movie(
        user_id=user_id,
        movie_id=movie_id,
        status=getattr(current, "status", None) or "liked",
        media_type=media_type,
        rating=rating,
    )
    try:
        await recommendation_service.rebuild_taste_profile(user_id)
    except Exception as exc:
        logger.exception("Taste rebuild failed after rating write: %s", exc)
    if hasattr(recommendation_service, "invalidate_user_cache"):
        await recommendation_service.invalidate_user_cache(user_id)
