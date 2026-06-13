from dataclasses import dataclass, field
from typing import Any

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

@dataclass
class MovieModel:
    movie_id: int
    title: str
    poster: str
    poster_path: str
    overview: str
    genre_names: list[str] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)
    directors: list[str] = field(default_factory=list)
    runtime_mins: int = 0
    media_type: str = "movie"
    year: str = ""
    rating: float = 0.0
    reason: str = ""
    tv_status: str = ""
    seasons: int = 0  # <--- Добавлено

    @classmethod
    def from_dict(cls, data: dict, reason: str = "") -> "MovieModel":
        """Фабрика для создания чистого объекта из грязного словаря (из БД или TMDB)."""
        # Нормализация постера
        raw_poster = data.get("poster_url") or data.get("poster_path") or ""
        poster = (
            raw_poster if str(raw_poster).startswith("http")
            else f"{TMDB_IMAGE_BASE}{raw_poster}" if raw_poster else ""
        )

        # Нормализация жанров
        raw_genres = data.get("genres_array") or data.get("genres") or []
        genre_names = [g["name"] if isinstance(g, dict) else str(g) for g in raw_genres]

        # Нормализация времени
        runtime = (
            data.get("runtime_mins") or data.get("runtime") or 
            (data.get("episode_run_time", [0])[0] if data.get("episode_run_time") else 0)
        )

        return cls(
            movie_id=data.get("id") or data.get("movie_id") or 0,
            title=data.get("title") or data.get("name") or "Без названия",
            poster=poster,
            poster_path=raw_poster,
            overview=data.get("overview", ""),
            genre_names=genre_names,
            actors=data.get("actors") or [],
            directors=data.get("directors") or [],
            runtime_mins=runtime,
            media_type=data.get("media_type", "movie"),
            year=str(data.get("year", "")),
            rating=float(data.get("rating_numeric") or data.get("vote_average") or 0.0),
            reason=reason or data.get("reason", ""),
            # Перехватываем пустоту, если в БД записался NULL
            tv_status=data.get("tv_status") or data.get("status") or "",
            seasons=data.get("seasons") or data.get("number_of_seasons") or 0 
        )

    def to_dict(self) -> dict:
        """Отдает чистый словарь для сериализатора."""
        return {
            "movie_id": self.movie_id,
            "title": self.title,
            "poster": self.poster,
            "poster_path": self.poster_path,
            "overview": self.overview,
            "genre_names": self.genre_names,
            "actors": self.actors,
            "directors": self.directors,
            "runtime_mins": self.runtime_mins,
            "media_type": self.media_type,
            "year": self.year,
            "rating": self.rating,
            "reason": self.reason,
            "tv_status": self.tv_status,
            "seasons": self.seasons # <--- Добавлено
        }