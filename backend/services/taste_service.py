from __future__ import annotations

from collections import Counter
from typing import Any

from config import db
from utils.genres import CANONICAL_TO_TMDB, TMDB_GENRES, normalize_title_genres, normalize_tmdb_genre

_COUNTRY_NAMES = {
    "US": "США", "GB": "Великобритания", "JP": "Япония", "KR": "Южная Корея",
    "FR": "Франция", "DE": "Германия", "IT": "Италия", "CA": "Канада",
    "AU": "Австралия", "IN": "Индия", "ES": "Испания", "RU": "Россия",
}


def _empty_summary() -> dict[str, Any]:
    return {
        "taste_source": "user_taste_profiles", "interaction_count": 0,
        "maturity": "empty", "maturity_label": "Вкус пока не сформирован", "confidence": 0.0,
        "genres": [], "keywords": [], "countries": [], "directors": [], "actors": [], "eras": [],
        "movie_vs_series": {"movies": 0, "series": 0, "total": 0},
        "country_coverage": {"known_titles": 0, "total_titles": 0, "coverage_percent": 0},
    }


def _maturity(count: int) -> tuple[str, str, float]:
    if count <= 0:
        return "empty", "Вкус пока не сформирован", 0.0
    if count <= 3:
        return "early", "Первые предпочтения", 0.35 * count / 3
    if count <= 9:
        return "forming", "Вкус формируется", 0.35 + 0.25 * (count - 3) / 6
    return "mature", "Сформировавшийся вкус", min(1.0, 0.60 + 0.40 * (count - 9) / 10)


def _distribution(value: Any) -> list[tuple[str, float]]:
    if not isinstance(value, dict):
        return []
    items = [(str(key), float(weight)) for key, weight in value.items()
             if isinstance(key, str) and isinstance(weight, (int, float)) and weight > 0]
    total = sum(weight for _, weight in items)
    return sorted(((key, weight / total * 100) for key, weight in items), key=lambda item: (-item[1], item[0])) if total else []


def _genre_items(value: Any) -> list[dict[str, Any]]:
    return [{"name": TMDB_GENRES.get(CANONICAL_TO_TMDB.get(key), key),
             "canonical": key, "share": round(share, 2)}
            for key, share in _distribution(value)]


def _country_label(value: str) -> str:
    return _COUNTRY_NAMES.get(value.upper(), value)


def _keyword_items(value: Any) -> list[dict[str, Any]]:
    result = []
    for key, share in _distribution(value):
        if len(key) < 3 or key.isdigit() or not any(char.isalpha() for char in key):
            continue
        result.append({"name": key.replace("_", " "), "share": round(share, 2)})
    return result[:8]


def _era_label(value: str) -> str:
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) >= 4:
        decade = int(digits[:4])
        return "Классика" if decade < 1980 else f"{str(decade)[:3]}0-е"
    return value


async def _collection_stats(user_id: int) -> tuple[dict[str, int], Counter, int, int]:
    try:
        response = await db._execute(
            db._client.table("user_movies").select("rating, media_type, movies(*)")
            .eq("user_id", user_id).eq("status", "liked")
        )
        rows = response.data if response and getattr(response, "data", None) else []
    except Exception:
        rows = []
    media = {"movies": 0, "series": 0}
    directors: Counter = Counter()
    known_countries = 0
    for row in rows:
        movie = row.get("movies") or {}
        if row.get("media_type") == "tv" or movie.get("media_type") == "tv":
            media["series"] += 1
        else:
            media["movies"] += 1
        for director in movie.get("directors") or []:
            if isinstance(director, dict):
                director = director.get("name")
            if isinstance(director, str) and director.strip():
                directors[director.strip()] += 1
        countries = movie.get("production_countries") or movie.get("origin_country") or []
        if countries:
            known_countries += 1
    return media, directors, known_countries, len(rows)


async def get_taste_summary(user_id: int) -> dict[str, Any]:
    try:
        profile = await db.get_taste_profile(user_id)
    except Exception:
        profile = None
    count = int((profile or {}).get("interaction_count") or 0)
    if not profile or count <= 0:
        return _empty_summary()

    maturity, maturity_label, confidence = _maturity(count)
    media, collection_directors, known_countries, total_titles = await _collection_stats(user_id)
    directors = [
        {"name": key, "share": round(share, 2), "count": collection_directors.get(key, 0)}
        for key, share in _distribution(profile.get("directors_jsonb"))[:5]
    ]
    countries = [{"name": _country_label(key), "share": round(share, 2)}
                 for key, share in _distribution(profile.get("countries_jsonb"))[:5]]
    eras = [{"name": _era_label(key), "share": round(share, 2)}
            for key, share in _distribution(profile.get("eras_jsonb"))[:6]]
    return {
        "taste_source": "user_taste_profiles", "interaction_count": count,
        "profile_version": int((profile or {}).get("profile_version") or 0),
        "maturity": maturity, "maturity_label": maturity_label,
        "confidence": round(confidence, 3), "genres": _genre_items(profile.get("genres_jsonb")),
        "keywords": _keyword_items(profile.get("keywords_jsonb")), "countries": countries,
        "directors": directors, "actors": [], "eras": eras,
        "movie_vs_series": {**media, "total": total_titles},
        "country_coverage": {
            "known_titles": known_countries, "total_titles": total_titles,
            "coverage_percent": round(known_countries / total_titles * 100, 2) if total_titles else 0,
        },
    }
