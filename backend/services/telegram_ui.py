"""Pure Telegram presentation helpers and compact callback protocol."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

VALID_MEDIA_TYPES = {"movie", "tv"}
VALID_STATUSES = {"none", "liked", "watchlist", "archive"}
VALID_ACTIONS = {"liked", "watchlist", "archive", "none"}


@dataclass(frozen=True, slots=True)
class CallbackAction:
    name: str
    args: tuple[str, ...] = ()


def _positive_int(value: str) -> bool:
    return value.isdecimal() and int(value) > 0


def parse_callback(data: str | None) -> CallbackAction | None:
    """Parse only the compact, allow-listed callback protocol."""
    if not isinstance(data, str) or not data or len(data) > 64:
        return None
    parts = data.split(":")
    if not parts or any(not part or len(part) > 32 for part in parts):
        return None

    if parts[0] == "m" and len(parts) == 3 and parts[1] in VALID_MEDIA_TYPES and _positive_int(parts[2]):
        return CallbackAction("movie", (parts[1], parts[2]))
    if parts[0] == "sm" and len(parts) == 3 and parts[1] in VALID_MEDIA_TYPES and _positive_int(parts[2]):
        return CallbackAction("search_movie", (parts[1], parts[2]))
    if parts[0] == "libm" and len(parts) == 6 and parts[1] in VALID_MEDIA_TYPES and _positive_int(parts[2]) and parts[3] in {"liked", "watchlist", "archive", "top", "recent"} and parts[4].isdecimal() and 0 <= int(parts[4]) <= 10000 and parts[5] in {"all", "movie", "tv"}:
        return CallbackAction("library_movie", tuple(parts[1:]))
    if parts[0] == "a" and len(parts) == 4 and parts[1] in VALID_ACTIONS and parts[2] in VALID_MEDIA_TYPES and _positive_int(parts[3]):
        return CallbackAction("media", (parts[1], parts[2], parts[3]))
    if parts[0] == "rate" and len(parts) == 4 and parts[1] in VALID_MEDIA_TYPES and _positive_int(parts[2]) and parts[3] in {"1", "2", "3", "4", "5"}:
        return CallbackAction("rate", (parts[1], parts[2], parts[3]))
    if parts[0] == "ratepick" and len(parts) == 3 and parts[1] in VALID_MEDIA_TYPES and _positive_int(parts[2]):
        return CallbackAction("ratepick", (parts[1], parts[2]))
    if parts[0] == "detail" and len(parts) >= 3 and parts[1] in VALID_MEDIA_TYPES and _positive_int(parts[2]):
        back_data = ":".join(parts[3:]) if len(parts) > 3 else ""
        if back_data and parse_callback(back_data) is None:
            return None
        return CallbackAction("detail", (parts[1], parts[2], back_data) if back_data else (parts[1], parts[2]))
    if parts[0] == "s" and len(parts) == 3 and parts[1] in {"all", "movie", "tv", "person"} and parts[2].isdecimal() and 1 <= int(parts[2]) <= 100:
        return CallbackAction("search", (parts[1], parts[2]))
    if parts[0] == "person" and len(parts) == 2 and _positive_int(parts[1]):
        return CallbackAction("person", (parts[1],))
    if parts[0] == "searchtype" and len(parts) == 2 and parts[1] in {"all", "movie", "tv", "person"}:
        return CallbackAction("searchtype", (parts[1],))
    if parts[0] == "credits" and len(parts) == 4 and _positive_int(parts[1]) and parts[2] in {"movie", "tv"} and parts[3].isdecimal() and int(parts[3]) <= 100:
        return CallbackAction("credits", (parts[1], parts[2], parts[3]))
    if parts[0] == "lib" and len(parts) in {3, 4} and parts[1] in {"liked", "watchlist", "archive", "top", "recent"} and parts[2].isdecimal() and 0 <= int(parts[2]) <= 10000:
        media = parts[3] if len(parts) == 4 else "all"
        if media in {"all", "movie", "tv"}:
            return CallbackAction("library", (parts[1], parts[2], media))
    if parts[0] == "rec" and len(parts) == 2 and parts[1] in {"next", "generate", "filters"}:
        return CallbackAction("recommendations", (parts[1],))
    if parts[0] == "rec" and len(parts) == 3 and parts[1] == "nav" and parts[2].isdecimal() and int(parts[2]) < 100:
        return CallbackAction("recommendations", ("nav", parts[2]))
    if parts[0] == "recact" and len(parts) == 4 and parts[1] in {"liked", "watchlist", "archive"} and parts[2] in VALID_MEDIA_TYPES and _positive_int(parts[3]):
        return CallbackAction("recommendation_action", (parts[1], parts[2], parts[3]))
    if parts[0] == "rf" and len(parts) == 3 and parts[1] in {"type", "rating", "minyear", "maxyear"}:
        if parts[1] == "type" and parts[2] not in {"mix", "movie", "tv"}:
            return None
        if parts[1] == "rating" and parts[2] not in {"6", "7", "7.5", "8", "8.5"}:
            return None
        return CallbackAction("recommendation_filter", (parts[1], parts[2]))
    if parts[0] == "tv" and len(parts) == 2 and _positive_int(parts[1]):
        return CallbackAction("tv", ("progress", parts[1]))
    if parts[0] == "tv" and len(parts) == 3 and _positive_int(parts[1]) and parts[2] == "tracked":
        return CallbackAction("tv", ("progress", parts[1], parts[2]))
    if parts[0] == "series" and len(parts) == 2 and parts[1] in {"menu", "continue", "all"}:
        return CallbackAction("series", (parts[1],))
    if parts[0] == "ep" and len(parts) == 5 and all(_positive_int(value) for value in parts[1:4]) and parts[4] in {"0", "1"} and int(parts[2]) <= 100 and int(parts[3]) <= 1000:
        return CallbackAction("episode", tuple(parts[1:]))
    if parts[0] == "sub" and len(parts) == 2 and _positive_int(parts[1]):
        return CallbackAction("subscription", (parts[1],))
    if parts[0] == "season" and len(parts) in {3, 4} and _positive_int(parts[1]) and parts[2].isdecimal() and 0 < int(parts[2]) <= 100:
        page = parts[3] if len(parts) == 4 else "1"
        if page.isdecimal() and 1 <= int(page) <= 100:
            return CallbackAction("season", (parts[1], parts[2], page))
    if parts[0] == "tracked" and len(parts) == 2 and parts[1].isdecimal() and 1 <= int(parts[1]) <= 10000:
        return CallbackAction("tracked", (parts[1],))
    if parts[0] == "profile" and len(parts) == 2 and parts[1] == "menu":
        return CallbackAction("profile", (parts[1],))
    return None


def _value(item: Any, *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
        if value not in (None, ""):
            return value
    return default


def render_movie_message(item: Any, user_status: str = "none", user_rating: int | None = None, *, full: bool = False) -> str:
    """Render a bounded, safe Telegram text card for search/list flows."""
    media_type = _value(item, "media_type", default="movie")
    title = html.escape(str(_value(item, "title", "name", default="Без названия")))
    year = html.escape(str(_value(item, "year", "release_date", "first_air_date", default="н/д"))[:10])
    rating = _value(item, "rating", "vote_average", "rating_numeric", default=0)
    try:
        rating_text = f"⭐ {float(rating):.1f}" if float(rating) else "⭐ н/д"
    except (TypeError, ValueError):
        rating_text = "⭐ н/д"
    genres = _value(item, "genre_names", "genres_array", "genres", default=[])
    if isinstance(genres, str):
        genres = [genres]
    genre_text = ", ".join(html.escape(str(value.get("name", "")) if isinstance(value, dict) else str(value)) for value in (genres or [])[:4])
    overview = html.escape(str(_value(item, "overview", default="") or "")).strip()
    if not full:
        overview = overview[:240].rstrip() + ("..." if len(overview) > 240 else "")
    status_labels = {"liked": "👀 Просмотрено", "watchlist": "🔖 В планах", "archive": "👎 Не интересно"}
    lines = [f"{'🎬' if media_type == 'movie' else '📺'} <b>{title}</b> ({year})", rating_text]
    if genre_text:
        lines.append(f"🎭 {genre_text}")
    if overview:
        lines.extend(["", f"📝 {overview}"])
    if status_labels.get(user_status):
        lines.extend(["", f"Ваш статус: {status_labels[user_status]}" + (f"\n⭐ {user_rating}/5" if user_rating else "")])
    return "\n".join(lines)[:4000]


def build_movie_keyboard(movie_id: int, user_status: str = "none", media_type: str = "movie", user_rating: int | None = None, *, back_data: str | None = None, webapp_url: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if user_status == "none":
        builder.button(text="✅ Посмотрел", callback_data=f"a:liked:{media_type}:{movie_id}")
        builder.button(text="🔖 В планы", callback_data=f"a:watchlist:{media_type}:{movie_id}")
        builder.button(text="👎 Не интересно", callback_data=f"a:archive:{media_type}:{movie_id}")
        builder.button(text="⭐ Оценить", callback_data=f"ratepick:{media_type}:{movie_id}")
    elif user_status == "watchlist":
        builder.button(text="✅ Посмотрел", callback_data=f"a:liked:{media_type}:{movie_id}")
        builder.button(text="👎 Не интересно", callback_data=f"a:archive:{media_type}:{movie_id}")
        builder.button(text="🗑 Убрать из планов", callback_data=f"a:none:{media_type}:{movie_id}")
    elif user_status == "liked":
        builder.button(text="⭐ Изменить оценку", callback_data=f"ratepick:{media_type}:{movie_id}")
        builder.button(text="🔖 В планы", callback_data=f"a:watchlist:{media_type}:{movie_id}")
        builder.button(text="🗑 Убрать из моего", callback_data=f"a:none:{media_type}:{movie_id}")
    else:
        builder.button(text="↩️ Вернуть", callback_data=f"a:none:{media_type}:{movie_id}")
    detail_callback = f"detail:{media_type}:{movie_id}"
    if back_data:
        detail_callback += f":{back_data}"
    builder.button(text="ℹ️ Подробнее", callback_data=detail_callback)
    if media_type == "tv":
        builder.button(text="📺 Эпизоды", callback_data=f"tv:{movie_id}")
    if webapp_url:
        from aiogram.types.web_app_info import WebAppInfo
        builder.button(text="🌐 Открыть", web_app=WebAppInfo(url=webapp_url))
    if back_data:
        builder.button(text="⬅️ Назад", callback_data=back_data)
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def build_library_page(items: list[Any], page: int, page_size: int = 5) -> tuple[list[Any], int, bool, bool]:
    page = max(0, int(page))
    page_size = max(1, min(int(page_size), 20))
    start = page * page_size
    return items[start:start + page_size], page, page > 0, start + page_size < len(items)
