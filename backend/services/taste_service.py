from __future__ import annotations

from collections import defaultdict
from typing import Any

from config import db

CANONICAL_GENRES = (
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama",
    "Family", "Fantasy", "History", "Horror", "Music", "Mystery", "Romance",
    "Science Fiction", "Thriller", "War", "Western", "Kids", "Reality", "News", "Talk", "Soap",
)

_ALIASES = {
    "action": "Action", "боевик": "Action",
    "adventure": "Adventure", "приключения": "Adventure",
    "animation": "Animation", "анимация": "Animation",
    "comedy": "Comedy", "комедия": "Comedy",
    "crime": "Crime", "криминал": "Crime",
    "documentary": "Documentary", "документальный": "Documentary",
    "drama": "Drama", "драма": "Drama",
    "family": "Family", "семейный": "Family",
    "fantasy": "Fantasy", "фэнтези": "Fantasy",
    "history": "History", "история": "History",
    "horror": "Horror", "ужасы": "Horror",
    "music": "Music", "музыка": "Music",
    "mystery": "Mystery", "детектив": "Mystery",
    "romance": "Romance", "мелодрама": "Romance",
    "science fiction": "Science Fiction", "sci-fi": "Science Fiction", "фантастика": "Science Fiction",
    "thriller": "Thriller", "триллер": "Thriller",
    "war": "War", "военный": "War",
    "western": "Western", "вестерн": "Western",
    "kids": "Kids", "детский": "Kids",
    "reality": "Reality", "реалити": "Reality",
    "news": "News", "новости": "News",
    "talk": "Talk", "ток-шоу": "Talk",
    "soap": "Soap", "мыльная опера": "Soap",
}

_COUNTRY_NAMES = {"US": "США", "GB": "Великобритания", "JP": "Япония", "KR": "Южная Корея", "FR": "Франция", "DE": "Германия", "IT": "Италия", "CA": "Канада", "AU": "Австралия", "IN": "Индия", "ES": "Испания", "RU": "Россия"}


def normalize_tmdb_genre(value: str | None) -> dict[str, float]:
    """Expand one TMDB label into canonical MMT genres and raw fractional weights."""
    if not isinstance(value, str):
        return {}
    label = value.strip().lower()
    if not label:
        return {}
    parts = [part.strip() for part in label.replace(" и ", "&").split("&") if part.strip()]
    if len(parts) > 1:
        share = 1.0 / len(parts)
    else:
        share = 1.0
    result: dict[str, float] = {}
    for part in parts:
        canonical = _ALIASES.get(part)
        if canonical:
            result[canonical] = result.get(canonical, 0.0) + share
    return result


def normalize_title_genres(values: list[str] | None) -> dict[str, float]:
    raw: dict[str, float] = defaultdict(float)
    for value in values or []:
        for genre, weight in normalize_tmdb_genre(value).items():
            raw[genre] += weight
    total = sum(raw.values())
    return {genre: weight / total for genre, weight in raw.items()} if total else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _names(value: Any) -> list[str]:
    result = []
    for item in _as_list(value):
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str) and name.strip():
            result.append(name.strip())
    return result


def _countries(movie: dict) -> list[str]:
    values = movie.get("production_countries") or movie.get("origin_country") or movie.get("countries")
    raw = []
    for item in _as_list(values):
        if isinstance(item, dict):
            value = item.get("iso_3166_1") or item.get("code") or item.get("name")
        else:
            value = item
        if isinstance(value, str) and value.strip():
            raw.append(value.strip())
    return [_COUNTRY_NAMES.get(value.upper(), value) for value in raw]


async def get_taste_summary(user_id: int) -> dict[str, Any]:
    response = await db._execute(
        db._client.table("user_movies")
        .select("rating, media_type, movies(*)")
        .eq("user_id", user_id)
        .eq("status", "liked")
    )
    rows = response.data if response and getattr(response, "data", None) else []
    genre_totals: dict[str, float] = defaultdict(float)
    directors: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "ratings": []})
    actors: dict[str, int] = defaultdict(int)
    eras: dict[str, int] = defaultdict(int)
    countries: dict[str, float] = defaultdict(float)
    movies = series = 0
    known_country_titles = 0

    for row in rows:
        movie = row.get("movies") or {}
        if row.get("media_type") == "tv" or movie.get("media_type") == "tv":
            series += 1
        else:
            movies += 1
        for genre, weight in normalize_title_genres(movie.get("genres_array") or movie.get("genres")).items():
            genre_totals[genre] += weight
        rating = row.get("rating")
        for director in _names(movie.get("directors")):
            directors[director]["count"] += 1
            if isinstance(rating, (int, float)) and 1 <= float(rating) <= 5:
                directors[director]["ratings"].append(float(rating))
        for actor in _names(movie.get("actors")):
            actors[actor] += 1
        try:
            year = int(str(movie.get("year") or "")[:4])
            if year >= 1900:
                eras[f"{year // 10 * 10}-е"] += 1
        except (TypeError, ValueError):
            pass
        movie_countries = _countries(movie)
        if movie_countries:
            known_country_titles += 1
            unique_countries = set(movie_countries)
            country_weight = 1.0 / len(unique_countries)
            for country in unique_countries:
                countries[country] += country_weight

    genre_total = sum(genre_totals.values())
    genre_result = [
        {"name": name, "share": round(value / genre_total * 100, 2)}
        for name, value in sorted(genre_totals.items(), key=lambda item: (-item[1], item[0]))
    ] if genre_total else []
    title_total = movies + series
    country_total = sum(countries.values())
    director_result = [
        {"name": name, "count": data["count"], "rating": round(sum(data["ratings"]) / len(data["ratings"]), 1) if data["ratings"] else None}
        for name, data in directors.items() if data["count"] >= 2
    ]
    director_result.sort(key=lambda item: (-item["count"], -(item["rating"] or 0), item["name"]))
    actor_result = [{"name": name, "count": count} for name, count in actors.items()]
    actor_result.sort(key=lambda item: (-item["count"], item["name"]))
    era_total = sum(eras.values())
    era_result = [{"name": name, "share": round(count / era_total * 100, 2)} for name, count in eras.items()] if era_total else []
    country_result = [{"name": name, "share": round(count / country_total * 100, 2)} for name, count in countries.items()] if country_total else []
    country_result.sort(key=lambda item: (-item["share"], item["name"]))
    return {
        "genres": genre_result,
        "movie_vs_series": {"movies": movies, "series": series, "total": title_total},
        "directors": director_result[:3],
        "actors": actor_result[:5],
        "eras": sorted(era_result, key=lambda item: (-item["share"], item["name"])),
        "countries": country_result[:5],
        "country_coverage": {"known_titles": known_country_titles, "total_titles": title_total, "coverage_percent": round(known_country_titles / title_total * 100, 2) if title_total else 0},
    }
