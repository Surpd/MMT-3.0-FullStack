from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from utils.genres import CANONICAL_TO_TMDB, normalize_title_genres, normalize_tmdb_genre, TMDB_GENRES

logger = logging.getLogger(__name__)

TMDB_GENRE_IDS = {genre_id: next(iter(normalize_tmdb_genre(label)), None) for genre_id, label in TMDB_GENRES.items()}
CANONICAL_GENRES = tuple(sorted(CANONICAL_TO_TMDB))
PROFILE_FIELDS = ("genres", "keywords", "directors", "countries", "eras")
FIELD_CAPS = {"genres": 64, "keywords": 30, "directors": 15, "countries": 10, "eras": 12}
LIKED_ALPHAS = {"genres": 0.09, "keywords": 0.07, "directors": 0.04, "countries": 0.025, "eras": 0.025}
WATCHLIST_ALPHAS = {"genres": 0.025, "keywords": 0.02, "directors": 0.01, "countries": 0.0075, "eras": 0.01}
RATING_MULTIPLIERS = {1: 0.0, 2: 0.25, 3: 0.5, 4: 0.8, 5: 1.0}
MAX_RETRIEVAL_REQUESTS = 18
MAX_RETRIEVAL_PAGES = 4
ADJACENT_GENRES = {
    "Crime": ("Mystery", "Thriller", "Drama"),
    "Mystery": ("Crime", "Thriller", "Drama"),
    "Thriller": ("Crime", "Mystery", "Action"),
    "Drama": ("Crime", "Romance", "History"),
    "Animation": ("Family", "Fantasy", "Adventure"),
    "Science Fiction": ("Fantasy", "Adventure", "Thriller"),
    "Fantasy": ("Adventure", "Science Fiction", "Family"),
    "Comedy": ("Romance", "Family", "Drama"),
    "Horror": ("Thriller", "Mystery", "Fantasy"),
}


@dataclass
class _RetrievalBudget:
    max_requests: int = MAX_RETRIEVAL_REQUESTS
    max_pages: int = MAX_RETRIEVAL_PAGES
    latency_budget_seconds: float = 2.2
    requests: int = 0
    pages_by_source: dict[str, int] | None = None
    requests_by_source: dict[str, int] | None = None
    started_at: float = field(default_factory=time.perf_counter)

    def reserve(self, page: bool = False, source: str = "default") -> bool:
        if time.perf_counter() - self.started_at >= self.latency_budget_seconds:
            return False
        if self.requests >= self.max_requests:
            return False
        if self.pages_by_source is None:
            self.pages_by_source = {}
        if self.requests_by_source is None:
            self.requests_by_source = {}
        group = source.split(":", 1)[0]
        source_limits = {"core_genre": 6, "adjacent_genre": 4, "similar": 3,
                         "recent": 2, "popular": 2, "exploration": 2}
        if self.requests_by_source.get(group, 0) >= source_limits.get(group, self.max_requests):
            return False
        if page and self.pages_by_source.get(source, 0) >= self.max_pages:
            return False
        self.requests += 1
        self.requests_by_source[group] = self.requests_by_source.get(group, 0) + 1
        if page:
            self.pages_by_source[source] = self.pages_by_source.get(source, 0) + 1
        return True


class RecommendationService:
    def __init__(self, db, tmdb, session_cache, recs_pool_cache):
        self.db = db
        self.tmdb = tmdb
        self.session_cache = session_cache
        self.recs_pool_cache = recs_pool_cache
        self._generation_locks: dict[int, asyncio.Lock] = {}

    async def invalidate_user_cache(self, user_id: int) -> None:
        if self.recs_pool_cache and hasattr(self.recs_pool_cache, "delete_prefix"):
            await self.recs_pool_cache.delete_prefix(f"user_recs_pool_{user_id}_")

    def _pool_key(self, user_id: int, target_type: str, min_year: int | None, max_year: int | None,
                  min_rating: float | None, taste_version: int = 0) -> str:
        return f"user_recs_pool_{user_id}_{target_type}_{min_year}_{max_year}_{min_rating}_v{taste_version}"

    def _rating_signal(self, rating: int | None) -> float:
        """Backward-compatible rating signal used by existing callers/tests."""
        return {1: -1.0, 2: -0.5, 3: 0.0, 4: 0.25, 5: 0.5}.get(rating, 0.0)

    @staticmethod
    def _canonical_genre(value: Any) -> str | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
            return TMDB_GENRE_IDS.get(int(value))
        if not isinstance(value, str):
            return None
        return next(iter(normalize_tmdb_genre(value)), None)

    @classmethod
    def _distribution(cls, values: Any, canonical: bool = False) -> dict[str, float]:
        if not isinstance(values, list):
            return {}
        if canonical and any(isinstance(value, str) and ("&" in value or " и " in value.lower()) for value in values):
            return normalize_title_genres(values)
        result: dict[str, float] = {}
        for value in values:
            if isinstance(value, dict):
                value = value.get("name") or value.get("id") or value.get("value")
            key = cls._canonical_genre(value) if canonical else (str(value).strip() if value is not None else "")
            if key:
                result[key] = result.get(key, 0.0) + 1.0
        return cls._normalize(result)

    @staticmethod
    def _normalize(values: dict[str, float], cap: int | None = None) -> dict[str, float]:
        clean = {str(k): float(v) for k, v in (values or {}).items() if isinstance(v, (int, float)) and v > 0}
        if cap and len(clean) > cap:
            clean = dict(sorted(clean.items(), key=lambda item: (-item[1], item[0]))[:cap])
        total = sum(clean.values())
        return {key: value / total for key, value in clean.items()} if total else {}

    @classmethod
    def _blend(cls, old: dict[str, float], item: dict[str, float], alpha: float, cap: int) -> dict[str, float]:
        return cls._normalize({key: old.get(key, 0.0) * (1 - alpha) + item.get(key, 0.0) * alpha
                               for key in set(old) | set(item)}, cap)

    @classmethod
    def _item_features(cls, movie: dict) -> dict[str, dict[str, float]]:
        genres = movie.get("genre_ids") or movie.get("genres_array") or movie.get("genres") or []
        keywords = movie.get("keywords") or movie.get("keywords_array") or []
        directors = movie.get("directors") or []
        countries = movie.get("production_countries") or movie.get("origin_country") or movie.get("countries") or []
        if isinstance(countries, str):
            countries = [countries]
        countries = [item.get("iso_3166_1") or item.get("code") or item.get("name") if isinstance(item, dict) else item for item in countries]
        release_date = movie.get("release_date") or movie.get("first_air_date") or movie.get("year") or ""
        try:
            year = int(str(release_date)[:4])
            eras = [f"{year // 10 * 10}s"] if year >= 1900 else []
        except (TypeError, ValueError):
            eras = []
        return {"genres": cls._distribution(genres, canonical=True), "keywords": cls._distribution(keywords),
                "directors": cls._distribution(directors), "countries": cls._distribution(countries),
                "eras": cls._distribution(eras)}

    @staticmethod
    def _dot(left: dict[str, float], right: dict[str, float]) -> float:
        return max(0.0, min(1.0, sum(value * right.get(key, 0.0) for key, value in left.items())))

    async def _load_user_rows(self, user_id: int) -> list[dict]:
        try:
            if hasattr(self.db, "get_user_recommendation_rows"):
                return await self.db.get_user_recommendation_rows(user_id)
            response = await self.db._execute(self.db._client.table("user_movies").select(
                "movie_id, status, media_type, rating, movies(*)").eq("user_id", user_id))
            return response.data if response and getattr(response, "data", None) else []
        except Exception as exc:
            logger.error("Recommendation context error: %s", exc)
            return []

    async def _load_taste_profile(self, user_id: int) -> dict | None:
        try:
            if hasattr(self.db, "get_taste_profile"):
                return await self.db.get_taste_profile(user_id)
        except Exception as exc:
            logger.warning("Taste profile unavailable for user %s: %s", user_id, exc)
        return None

    async def _taste_version(self, user_id: int) -> int:
        profile = await self._load_taste_profile(user_id)
        try:
            return max(0, int((profile or {}).get("profile_version") or 0))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _profile_from_rows(cls, rows: list[dict]) -> dict[str, Any]:
        profile: dict[str, Any] = {field: {} for field in PROFILE_FIELDS}
        profile.update({"movie_modifiers": {}, "tv_modifiers": {}, "interaction_count": 0, "profile_version": 0})
        for row in rows:
            status = row.get("status")
            if status not in {"liked", "watchlist"}:
                continue
            movie = row.get("movies") or {}
            multiplier = RATING_MULTIPLIERS.get(row.get("rating"), 1.0) if status == "liked" else 1.0
            if multiplier <= 0:
                continue
            alphas = LIKED_ALPHAS if status == "liked" else WATCHLIST_ALPHAS
            features = cls._item_features(movie)
            media_type = row.get("media_type") or movie.get("media_type") or "movie"
            for field in PROFILE_FIELDS:
                alpha = alphas[field] * multiplier
                profile[field] = cls._blend(profile[field], features[field], alpha, FIELD_CAPS[field])
                modifier_key = f"{media_type}_modifiers"
                profile[modifier_key][field] = cls._blend(profile[modifier_key].get(field, {}), features[field], alpha, FIELD_CAPS[field])
            profile["interaction_count"] += 1
        return profile

    @classmethod
    def _bootstrap_profile_from_rows(cls, rows: list[dict]) -> dict[str, Any]:
        """Build an order-independent snapshot from the current user state.

        Bootstrap is intentionally different from an interaction update: all
        current rows are aggregated first, then every distribution is capped
        and normalized once. This avoids replaying an unreliable historical
        event order through EMA.
        """
        accumulators: dict[str, dict[str, float]] = {field: {} for field in PROFILE_FIELDS}
        modifiers: dict[str, dict[str, dict[str, float]]] = {"movie": {}, "tv": {}}
        interaction_count = 0
        for row in rows or []:
            status = row.get("status")
            if status not in {"liked", "watchlist"}:
                continue
            multiplier = RATING_MULTIPLIERS.get(row.get("rating"), 1.0) if status == "liked" else 1.0
            if multiplier <= 0:
                continue
            features = cls._item_features(row.get("movies") or {})
            alphas = LIKED_ALPHAS if status == "liked" else WATCHLIST_ALPHAS
            media_type = row.get("media_type") or (row.get("movies") or {}).get("media_type") or "movie"
            media_accumulator = modifiers.setdefault(media_type, {})
            for field in PROFILE_FIELDS:
                contribution = alphas[field] * multiplier
                for key, value in features[field].items():
                    accumulators[field][key] = accumulators[field].get(key, 0.0) + contribution * value
                    field_accumulator = media_accumulator.setdefault(field, {})
                    field_accumulator[key] = field_accumulator.get(key, 0.0) + contribution * value
            interaction_count += 1
        profile: dict[str, Any] = {
            field: cls._normalize(accumulators[field], FIELD_CAPS[field]) for field in PROFILE_FIELDS
        }
        profile["movie_modifiers"] = {
            field: cls._normalize(modifiers["movie"].get(field, {}), FIELD_CAPS[field])
            for field in PROFILE_FIELDS
        }
        profile["tv_modifiers"] = {
            field: cls._normalize(modifiers["tv"].get(field, {}), FIELD_CAPS[field])
            for field in PROFILE_FIELDS
        }
        profile.update({"interaction_count": interaction_count, "profile_version": 0})
        return profile

    async def _get_user_context(self, user_id: int):
        rows = await self._load_user_rows(user_id)
        stored = await self._load_taste_profile(user_id)
        profile = stored or self._profile_from_rows(rows)
        genre_weights = self._normalize(profile.get("genres_jsonb") or profile.get("genres") or {}, FIELD_CAPS["genres"])
        top_canonical = sorted(genre_weights, key=lambda key: (-genre_weights[key], key))[:5]
        top_genres = [CANONICAL_TO_TMDB[key] for key in top_canonical if key in CANONICAL_TO_TMDB]
        recent_liked_ids = [{"id": row.get("movie_id"), "type": row.get("media_type") or "movie"}
                            for row in rows if row.get("status") == "liked" and row.get("movie_id") is not None][-3:]
        blacklist = {(row.get("movie_id"), row.get("media_type") or "movie") for row in rows if row.get("movie_id") is not None}
        positive_count = sum(
            row.get("status") == "watchlist"
            or (row.get("status") == "liked" and RATING_MULTIPLIERS.get(row.get("rating"), 1.0) > 0)
            for row in rows
        )
        if stored is not None:
            try:
                positive_count = max(0, int(stored.get("interaction_count") or 0))
            except (TypeError, ValueError):
                positive_count = 0
        return genre_weights, top_genres, recent_liked_ids, blacklist, positive_count, rows

    @staticmethod
    def _movie_ratio(rows: list[dict]) -> float:
        positive = [row for row in rows if row.get("status") in {"liked", "watchlist"}]
        if len(positive) < 4:
            return 0.70
        tv_share = sum((row.get("media_type") or "movie") == "tv" for row in positive) / len(positive)
        tv_ratio = max(0.20, min(0.45, 0.30 + 0.50 * (tv_share - 0.30)))
        return 1.0 - tv_ratio

    @staticmethod
    def _filter_blacklist(results: list[dict], blacklist: set) -> list[dict]:
        return [movie for movie in (results or []) if movie.get("id") is not None and
                (movie.get("id"), movie.get("media_type") or "movie") not in blacklist]

    @staticmethod
    def _filter_recently_shown(results: list[dict], shown_ids: set[tuple]) -> list[dict]:
        return [movie for movie in results or [] if (movie.get("id"), movie.get("media_type") or "movie") not in shown_ids]

    @staticmethod
    def _passes_hard_filters(movie: dict, min_year: int | None, max_year: int | None, min_rating: float | None) -> bool:
        try:
            if min_rating is not None and float(movie.get("vote_average") or 0) < min_rating:
                return False
        except (TypeError, ValueError):
            return False
        if min_year is None and max_year is None:
            return True
        release_date = movie.get("release_date") or movie.get("first_air_date") or ""
        try:
            release_year = int(str(release_date)[:4])
        except (TypeError, ValueError):
            return False
        return (min_year is None or release_year >= min_year) and (max_year is None or release_year <= max_year)

    def _merge_candidates(self, raw_candidates: dict[tuple, dict], items: list[dict], source: str | None = None) -> None:
        for movie in items or []:
            movie_id = movie.get("id")
            if movie_id is None:
                continue
            media_type = movie.get("media_type") or "movie"
            key = (movie_id, media_type)
            existing = raw_candidates.setdefault(key, dict(movie))
            existing.setdefault("_sources", [])
            if source and source not in existing["_sources"]:
                existing["_sources"].append(source)

    async def _discover_pages(self, top_genres: list, blacklist: set, media_type: str,
                              min_year: int | None, max_year: int | None, min_rating: float | None,
                              sort_by: str = "popularity.desc", pages: int = 2,
                              source: str = "discover", budget: _RetrievalBudget | None = None,
                              year_span: int | None = None) -> list[dict]:
        current_year = max_year or datetime.now().year
        start_year = min_year if min_year is not None else (
            max_year - (year_span or 15) if max_year is not None else current_year - (year_span or 15)
        )
        filters = {"vote_count.gte": 300, "vote_average.gte": min_rating if min_rating is not None else 6.0}
        if top_genres:
            filters["with_genres"] = top_genres
        results = []
        max_page = min(pages, (budget.max_pages if budget else pages))
        for page in range(1, max_page + 1):
            if budget and not budget.reserve(page=True, source=f"{source}:{media_type}"):
                break
            try:
                payload = await self.tmdb.discover_with_filters(media_type=media_type,
                    year_from=start_year, year_to=current_year,
                    sort_by=sort_by, page=page, **filters)
            except Exception as exc:
                logger.warning("Discover source failed media=%s source=%s page=%s: %s", media_type, source, page, exc)
                continue
            page_items = (payload or {}).get("results", []) if isinstance(payload, dict) else []
            for movie in page_items:
                if isinstance(movie, dict):
                    movie.setdefault("media_type", media_type)
            results.extend(movie for movie in self._filter_blacklist(page_items, blacklist)
                           if self._passes_hard_filters(movie, min_year, max_year, min_rating))
            total_pages = (payload or {}).get("total_pages") if isinstance(payload, dict) else None
            if total_pages and page >= min(int(total_pages), max_page):
                break
        return results

    async def _discover_with_cascade(self, top_genres: list, blacklist: set, media_type: str,
                                     min_year: int | None = None, max_year: int | None = None,
                                     min_rating: float | None = None, budget: _RetrievalBudget | None = None) -> list[dict]:
        # Kept as a compatibility wrapper for callers/tests; sources are now
        # additive and the fallback never relaxes explicit hard filters.
        results = await self._discover_pages(top_genres, blacklist, media_type, min_year, max_year, min_rating,
                                              pages=2, source="core", budget=budget)
        if not results:
            results = await self._discover_pages([], blacklist, media_type, min_year, max_year, min_rating,
                                                  sort_by="vote_count.desc", pages=2, source="quality_fallback", budget=budget)
        return results

    async def _fetch_similar(self, recent_liked_ids: list, blacklist: set, target_type: str,
                             min_year: int | None, max_year: int | None, min_rating: float | None,
                             budget: _RetrievalBudget | None = None) -> list[dict]:
        async def one(seed: dict) -> list[dict]:
            seed_type = seed.get("type") or "movie"
            if target_type != "mix" and seed_type != target_type:
                return []
            try:
                if budget and not budget.reserve(source=f"similar:{seed_type}"):
                    return []
                try:
                    payload = await self.tmdb.get_recommendations(seed["id"], seed_type, page=1)
                except TypeError:
                    payload = await self.tmdb.get_recommendations(seed["id"], seed_type)
                items = []
                for movie in ((payload or {}).get("results", []) if isinstance(payload, dict) else [])[:20]:
                    movie["media_type"] = seed_type
                    if self._passes_hard_filters(movie, min_year, max_year, min_rating):
                        items.extend(self._filter_blacklist([movie], blacklist))
                return items
            except Exception as exc:
                logger.warning("Similar recommendations failed for %s/%s: %s", seed_type, seed.get("id"), exc)
                return []
        batches = await asyncio.gather(*(one(seed) for seed in recent_liked_ids), return_exceptions=True)
        return [movie for batch in batches if isinstance(batch, list) for movie in batch]

    async def _fetch_recent_and_popular(self, blacklist: set, target_type: str, min_year: int | None,
                                        max_year: int | None, min_rating: float | None,
                                        budget: _RetrievalBudget | None = None) -> tuple[list[dict], list[dict]]:
        media_types = ["movie", "tv"] if target_type == "mix" else [target_type]
        current_year = datetime.now().year
        async def fetch(media_type: str, sort_by: str, years: int, source: str) -> list[dict]:
            return await self._discover_pages([], blacklist, media_type, min_year, max_year, min_rating,
                                              sort_by=sort_by, pages=2, source=source, budget=budget, year_span=years)
        recent, popular = await asyncio.gather(
            asyncio.gather(*(fetch(mt, "primary_release_date.desc" if mt == "movie" else "first_air_date.desc", 2, "recent") for mt in media_types), return_exceptions=True),
            asyncio.gather(*(fetch(mt, "popularity.desc", 15, "popular") for mt in media_types), return_exceptions=True))
        return ([movie for batch in recent if isinstance(batch, list) for movie in batch],
                [movie for batch in popular if isinstance(batch, list) for movie in batch])

    async def _fetch_candidates_from_tmdb(self, top_genres: list, recent_liked_ids: list, blacklist: set,
                                          target_type: str = "mix", min_year: int | None = None,
                                          max_year: int | None = None, min_rating: float | None = None) -> list[dict]:
        media_types = ["movie", "tv"] if target_type == "mix" else [target_type]
        budget = _RetrievalBudget()
        strongest = top_genres[:2]
        adjacent = []
        for canonical in top_genres:
            adjacent.extend(ADJACENT_GENRES.get(canonical, ()))
        adjacent = list(dict.fromkeys(genre for genre in adjacent if genre not in top_genres))[:3]
        genre_batches, adjacent_batches, similar, recent_popular = await asyncio.gather(
            asyncio.gather(*(self._discover_pages(strongest, blacklist, mt, min_year, max_year, min_rating,
                                                   pages=MAX_RETRIEVAL_PAGES, source="core_genre", budget=budget) for mt in media_types), return_exceptions=True),
            asyncio.gather(*(self._discover_pages([CANONICAL_TO_TMDB[g]], blacklist, mt, min_year, max_year, min_rating,
                                                   pages=2, source="adjacent_genre", budget=budget)
                            for g in adjacent for mt in media_types), return_exceptions=True),
            self._fetch_similar(recent_liked_ids, blacklist, target_type, min_year, max_year, min_rating, budget),
            self._fetch_recent_and_popular(blacklist, target_type, min_year, max_year, min_rating, budget), return_exceptions=True)
        raw_candidates: dict[tuple, dict] = {}
        if isinstance(genre_batches, list):
            for batch in genre_batches:
                if isinstance(batch, list): self._merge_candidates(raw_candidates, batch, "genre_discover")
        if isinstance(adjacent_batches, list):
            for batch in adjacent_batches:
                if isinstance(batch, list): self._merge_candidates(raw_candidates, batch, "adjacent_genre")
        if isinstance(similar, list): self._merge_candidates(raw_candidates, similar, "liked_seed")
        if isinstance(recent_popular, tuple):
            self._merge_candidates(raw_candidates, recent_popular[0], "recent_release")
            self._merge_candidates(raw_candidates, recent_popular[1], "popular")
        # Exploration is a controlled adjacent-genre source, not random noise.
        if adjacent and budget.requests < budget.max_requests:
            exploration_batches = await asyncio.gather(*(
                self._discover_pages([CANONICAL_TO_TMDB[adjacent[0]]], blacklist, media_type,
                                      min_year, max_year, min_rating, sort_by="vote_average.desc",
                                      pages=2, source="exploration", budget=budget)
                for media_type in media_types
            ), return_exceptions=True)
            for batch in exploration_batches:
                if isinstance(batch, list):
                    self._merge_candidates(raw_candidates, batch, "exploration")
        logger.info("recommendation_retrieval requests=%s candidates=%s", budget.requests, len(raw_candidates))
        return list(raw_candidates.values())

    async def _join_local_metadata(self, candidates: list[dict]) -> list[dict]:
        ids = [movie.get("id") for movie in candidates if movie.get("id") is not None]
        if not ids or not hasattr(self.db, "get_movies_by_ids"):
            return candidates
        try:
            rows = await self.db.get_movies_by_ids(ids)
        except Exception as exc:
            logger.warning("Local recommendation metadata unavailable: %s", exc)
            return candidates
        by_key = {(row.get("id"), row.get("media_type") or "movie"): row for row in rows or []}
        return [{**(by_key.get((movie.get("id"), movie.get("media_type") or "movie")) or {}), **movie} for movie in candidates]

    @staticmethod
    def _taste_confidence(interaction_count: int) -> float:
        """Blend taste in gradually so one title cannot lock the deck."""
        if interaction_count <= 0:
            return 0.0
        if interaction_count <= 3:
            return 0.35 * interaction_count / 3.0
        if interaction_count <= 9:
            return 0.35 + 0.25 * (interaction_count - 3) / 6.0
        return min(1.0, 0.60 + 0.40 * (interaction_count - 9) / 10.0)

    def _score_candidates(self, candidates: list[dict], genre_weights: dict, recent_liked_ids: list,
                          session_data: dict, profile: dict | None = None,
                          interaction_count: int | None = None) -> list[dict]:
        profile = profile or {field: {} for field in PROFILE_FIELDS}
        scored = []
        for movie in candidates or []:
            features = self._item_features(movie)
            modifier = profile.get(f"{movie.get('media_type') or 'movie'}_modifiers") or {}
            genre_global = self._dot(genre_weights, features["genres"])
            genre_specific = self._dot(modifier.get("genres") or {}, features["genres"])
            genre_match = 0.7 * genre_global + 0.3 * genre_specific
            keyword_match = 0.7 * self._dot(profile.get("keywords") or {}, features["keywords"]) + 0.3 * self._dot(modifier.get("keywords") or {}, features["keywords"])
            director_match = 0.7 * self._dot(profile.get("directors") or {}, features["directors"]) + 0.3 * self._dot(modifier.get("directors") or {}, features["directors"])
            country_match = 0.7 * self._dot(profile.get("countries") or {}, features["countries"]) + 0.3 * self._dot(modifier.get("countries") or {}, features["countries"])
            era_match = 0.7 * self._dot(profile.get("eras") or {}, features["eras"]) + 0.3 * self._dot(modifier.get("eras") or {}, features["eras"])
            specific_matches = [
                self._dot(modifier.get(field) or {}, features[field]) for field in PROFILE_FIELDS
            ]
            media_modifier = sum(specific_matches) / len(specific_matches)
            rating = max(0.0, min(10.0, float(movie.get("vote_average") or 0)))
            try: votes = max(0, int(movie.get("vote_count") or movie.get("tmdb_vote_count") or 0))
            except (TypeError, ValueError): votes = 0
            confidence = min(1.0, math.log10(votes + 1) / 5.0) if votes else 0.0
            quality = (rating / 10.0) * confidence
            personal_match = (0.35 * genre_match + 0.20 * keyword_match + 0.15 * director_match
                              + 0.10 * country_match + 0.10 * era_match + 0.10 * media_modifier)
            confidence = 1.0 if interaction_count is None else self._taste_confidence(interaction_count)
            taste_match = confidence * personal_match
            exploration = 1.0 if features["genres"] and genre_match > 0 and not set(features["genres"]).issubset(genre_weights) else 0.0
            # A skip excludes the concrete title only; one skip is not a dislike signal.
            skip_penalty = 0.0
            breakdown = {"genres": round(genre_match, 4), "keywords": round(keyword_match, 4), "director": round(director_match, 4),
                         "country": round(country_match, 4), "era": round(era_match, 4), "media_modifier": round(media_modifier, 4),
                         "taste_match": round(taste_match, 4), "quality": round(quality, 4),
                         "exploration": round(exploration, 4), "skip_penalty": round(skip_penalty, 4)}
            movie["score_breakdown"] = breakdown
            movie["final_score"] = (taste_match + 0.10 * quality + 0.05 * exploration - skip_penalty)
            movie["bucket"] = self._classify_bucket(movie)
            movie["reason_code"] = self._reason_code(breakdown, movie["bucket"])
            movie["reason"] = self._reason_text(movie["reason_code"])
            scored.append(movie)
        return scored

    @staticmethod
    def _classify_bucket(movie: dict) -> str:
        breakdown = movie.get("score_breakdown") or {}
        taste = float(breakdown.get("taste_match") or 0)
        feature_touch = max(float(breakdown.get(key) or 0) for key in ("genres", "keywords", "director", "country", "era"))
        quality = float(breakdown.get("quality") or 0)
        sources = set(movie.get("_sources") or [])
        if taste >= 0.30 or float(breakdown.get("genres") or 0) >= 0.45:
            return "core"
        if feature_touch >= 0.12 and ("adjacent_genre" in sources or taste >= 0.12):
            return "adjacent"
        if feature_touch > 0 and quality >= 0.30:
            return "discovery"
        # A pure popularity/quality fallback is not called discovery: discovery
        # must have a real metadata touchpoint with the profile.
        return "adjacent" if feature_touch > 0 else "core"

    @staticmethod
    def _reason_code(breakdown: dict[str, float], bucket: str = "core") -> str:
        if bucket == "adjacent":
            return "adjacent"
        if bucket == "discovery":
            return "discovery"
        candidates = {key: value for key, value in breakdown.items()
                      if key not in {"skip_penalty", "exploration", "taste_match", "media_modifier"} and value > 0}
        return max(candidates, key=candidates.get) if candidates else "fallback"

    @staticmethod
    def _reason_text(code: str) -> str:
        return {"genres": "В ваших любимых жанрах", "keywords": "Совпадает с любимыми темами",
                "director": "Вам часто нравятся фильмы этого режиссёра", "country": "Похоже на знакомое вам кино",
                "era": "Похоже на фильмы из любимого периода", "quality": "Высокое качество с надёжной оценкой",
                "adjacent": "Попробуйте близкое к вашим любимым темам",
                "discovery": "Попробуйте что-то немного новое",
                "fallback": "Рекомендация для вас"}.get(code, "Рекомендация для вас")

    @staticmethod
    def _select_buckets(ranked_candidates: list[dict], batch_size: int = 10,
                        interaction_count: int | None = None) -> list[dict]:
        buckets = {name: [] for name in ("core", "adjacent", "discovery")}
        for item in sorted(ranked_candidates, key=lambda value: value.get("final_score", 0), reverse=True):
            buckets.setdefault(item.get("bucket", "core"), []).append(item)
        if interaction_count is None or interaction_count >= 10:
            target_values = (7, 2, 1)
        elif interaction_count <= 3:
            target_values = (4, 4, 2)
        else:
            target_values = (6, 3, 1)
        targets = {"core": min(target_values[0], batch_size),
                   "adjacent": min(target_values[1], max(0, batch_size - target_values[0])),
                   "discovery": min(target_values[2], max(0, batch_size - target_values[0] - target_values[1]))}
        selected = []
        used = set()
        for bucket in ("core", "adjacent", "discovery"):
            for item in buckets[bucket][:targets[bucket]]:
                key = (item.get("id"), item.get("media_type") or "movie")
                if key not in used:
                    used.add(key)
                    selected.append(item)
        remaining = [item for item in sorted(ranked_candidates, key=lambda value: value.get("final_score", 0), reverse=True)
                     if (item.get("id"), item.get("media_type") or "movie") not in used]
        selected.extend(remaining[:max(0, batch_size - len(selected))])
        return selected[:batch_size]

    @staticmethod
    def _apply_diversity_and_protect_top(ranked_candidates: list[dict], target_type: str = "mix",
                                         movie_ratio: float = 0.70) -> list[dict]:
        if not ranked_candidates: return []
        protected, rest, selected = ranked_candidates[:5], ranked_candidates[5:], []
        selected.extend(protected)
        feature_cache = {id(item): RecommendationService._item_features(item) for item in ranked_candidates}
        genre_sets = {item_id: set(features["genres"]) for item_id, features in feature_cache.items()}
        keyword_sets = {item_id: set(features["keywords"]) for item_id, features in feature_cache.items()}
        director_sets = {id(item): set(item.get("directors") or []) for item in ranked_candidates}
        source_sets = {id(item): set(item.get("_sources") or []) for item in ranked_candidates}
        selected_sources = set().union(*(source_sets[id(item)] for item in protected)) if protected else set()
        selected_collections = {item.get("belongs_to_collection") for item in protected if item.get("belongs_to_collection")}
        while rest:
            def adjusted(item):
                penalty = 0.12 * sum(1 for chosen in selected if director_sets[id(item)] & director_sets[id(chosen)])
                penalty += 0.04 * sum(1 for chosen in selected if genre_sets[id(item)] & genre_sets[id(chosen)])
                penalty += 0.025 * sum(1 for chosen in selected if keyword_sets[id(item)] & keyword_sets[id(chosen)])
                if item.get("belongs_to_collection") in selected_collections:
                    penalty += 0.10
                if source_sets[id(item)] & selected_sources:
                    penalty += 0.015
                return float(item.get("final_score") or 0) - penalty
            best = max(rest, key=adjusted)
            rest.remove(best)
            selected.append(best)
            selected_sources.update(source_sets[id(best)])
            if best.get("belongs_to_collection"):
                selected_collections.add(best["belongs_to_collection"])
        if target_type != "mix": return selected
        movies = [item for item in selected if (item.get("media_type") or "movie") == "movie"]
        shows = [item for item in selected if (item.get("media_type") or "movie") == "tv"]
        if target_type != "mix":
            return selected
        target_movies = min(len(movies), max(0, round(len(selected) * max(0.55, min(0.80, movie_ratio)))))
        target_tv = len(selected) - target_movies
        target_tv = min(len(shows), target_tv)
        target_movies = min(len(movies), len(selected) - target_tv)
        result = []
        movie_used = tv_used = 0
        accumulator = 0.0
        while movies or shows:
            accumulator += movie_ratio
            want_movie = accumulator >= 1.0
            if want_movie and movies and movie_used < target_movies:
                result.append(movies.pop(0)); movie_used += 1; accumulator -= 1.0
            elif shows and tv_used < target_tv:
                result.append(shows.pop(0)); tv_used += 1
            elif movies:
                result.append(movies.pop(0)); movie_used += 1
            else:
                result.append(shows.pop(0)); tv_used += 1
        return result

    async def _fetch_novice_hits(self, blacklist: set, target_type: str, top_genres: list,
                                 min_year: int | None, max_year: int | None, min_rating: float | None,
                                 movie_ratio: float = 0.70) -> list[dict]:
        media_types = ["movie", "tv"] if target_type == "mix" else [target_type]
        async def fetch(media_type):
            payload = await self.tmdb.discover_with_filters(media_type=media_type, sort_by="vote_count.desc", page=1,
                **{"vote_average.gte": min_rating if min_rating is not None else 7.8, "vote_count.gte": 10000},
                **({"year_from": min_year, "year_to": max_year or datetime.now().year} if min_year is not None else {}))
            items = (payload or {}).get("results", []) if isinstance(payload, dict) else []
            return [movie for movie in self._filter_blacklist(items, blacklist) if self._passes_hard_filters(movie, min_year, max_year, min_rating)]
        batches = await asyncio.gather(*(fetch(mt) for mt in media_types), return_exceptions=True)
        results = [movie for batch in batches if isinstance(batch, list) for movie in batch]
        for movie in results: movie["reason"], movie["final_score"] = "Популярный старт для нового профиля", float(movie.get("vote_average") or 0) / 10
        if target_type != "mix": return results[:10]
        movies = [item for item in results if item.get("media_type") == "movie"]
        shows = [item for item in results if item.get("media_type") == "tv"]
        return self._apply_diversity_and_protect_top(results, "mix", movie_ratio)

    async def update_taste_profile(self, user_id: int, movie_id: int, media_type: str, status: str, rating: int | None = None) -> None:
        if not hasattr(self.db, "upsert_taste_profile"):
            return
        if status == "archive":
            stored = await self._load_taste_profile(user_id)
            if stored:
                snapshot = {"user_id": user_id, **{
                    f"{field}_jsonb": stored.get(f"{field}_jsonb") or {} for field in PROFILE_FIELDS
                }, "movie_modifiers_jsonb": stored.get("movie_modifiers_jsonb") or {},
                    "tv_modifiers_jsonb": stored.get("tv_modifiers_jsonb") or {},
                    "interaction_count": int(stored.get("interaction_count") or 0),
                    "profile_version": int(stored.get("profile_version") or 0) + 1}
                await self.db.upsert_taste_profile(snapshot)
            return
        if status not in {"liked", "watchlist"}:
            return
        try:
            movie = await self.db.get_movie(movie_id, media_type) or {}
        except TypeError:
            movie = await self.db.get_movie(movie_id) or {}
        stored = await self._load_taste_profile(user_id)
        if stored:
            profile = {field: stored.get(f"{field}_jsonb") or {} for field in PROFILE_FIELDS}
            profile.update({"movie_modifiers": stored.get("movie_modifiers_jsonb") or {}, "tv_modifiers": stored.get("tv_modifiers_jsonb") or {}})
            count, version = int(stored.get("interaction_count") or 0), int(stored.get("profile_version") or 0)
        else:
            # The API writes user_movies before this call. Exclude that row from
            # the fallback snapshot so the current interaction is blended once.
            rows = await self._load_user_rows(user_id)
            rows = [row for row in rows if not (
                row.get("movie_id") == movie_id and (row.get("media_type") or "movie") == (media_type or "movie")
            )]
            profile = self._profile_from_rows(rows)
            count, version = profile.pop("interaction_count"), profile.pop("profile_version")
        movie["media_type"] = media_type or movie.get("media_type") or "movie"
        multiplier = RATING_MULTIPLIERS.get(rating, 1.0) if status == "liked" else 1.0
        if multiplier <= 0: return
        alphas = LIKED_ALPHAS if status == "liked" else WATCHLIST_ALPHAS
        modifier_key = f"{movie['media_type']}_modifiers"
        for field in PROFILE_FIELDS:
            alpha = alphas[field] * multiplier
            features = self._item_features(movie)
            profile[field] = self._blend(profile[field], features[field], alpha, FIELD_CAPS[field])
            profile[modifier_key][field] = self._blend(profile[modifier_key].get(field, {}), features[field], alpha, FIELD_CAPS[field])
        await self.db.upsert_taste_profile({"user_id": user_id, "genres_jsonb": profile["genres"], "keywords_jsonb": profile["keywords"],
            "directors_jsonb": profile["directors"], "countries_jsonb": profile["countries"], "eras_jsonb": profile["eras"],
            "movie_modifiers_jsonb": profile["movie_modifiers"], "tv_modifiers_jsonb": profile["tv_modifiers"],
            "interaction_count": count + 1, "profile_version": version + 1})

    async def rebuild_taste_profile(self, user_id: int) -> None:
        """Rebuild the derived snapshot when an existing item's rating changes."""
        if not hasattr(self.db, "upsert_taste_profile"):
            return
        profile = self._bootstrap_profile_from_rows(await self._load_user_rows(user_id))
        stored = await self._load_taste_profile(user_id)
        await self.db.upsert_taste_profile({"user_id": user_id, "genres_jsonb": profile["genres"], "keywords_jsonb": profile["keywords"],
            "directors_jsonb": profile["directors"], "countries_jsonb": profile["countries"], "eras_jsonb": profile["eras"],
            "movie_modifiers_jsonb": profile["movie_modifiers"], "tv_modifiers_jsonb": profile["tv_modifiers"],
            "interaction_count": profile["interaction_count"], "profile_version": int((stored or {}).get("profile_version") or 0) + 1})

    async def bootstrap_taste_profile(self, user_id: int, rows: list[dict] | None = None) -> dict[str, Any]:
        """Persist a deterministic snapshot for an existing user."""
        if not hasattr(self.db, "upsert_taste_profile"):
            return {}
        source_rows = rows if rows is not None else await self._load_user_rows(user_id)
        profile = self._bootstrap_profile_from_rows(source_rows)
        stored = await self._load_taste_profile(user_id)
        version = int((stored or {}).get("profile_version") or 0) + 1
        payload = {"user_id": user_id,
                   **{f"{field}_jsonb": profile[field] for field in PROFILE_FIELDS},
                   "movie_modifiers_jsonb": profile["movie_modifiers"],
                   "tv_modifiers_jsonb": profile["tv_modifiers"],
                   "interaction_count": profile["interaction_count"],
                   "profile_version": version}
        await self.db.upsert_taste_profile(payload)
        return {**profile, "profile_version": version}

    async def get_next_movies(self, user_id: int, cursor: int = 0, force_refresh: bool = False, target_type: str = "mix",
                              min_year: int | None = None, max_year: int | None = None, min_rating: float | None = None) -> tuple[list[dict], bool]:
        lock = self._generation_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            return await self._get_next_movies_impl(user_id, cursor, force_refresh, target_type, min_year, max_year, min_rating)

    async def _get_next_movies_impl(self, user_id: int, cursor: int = 0, force_refresh: bool = False, target_type: str = "mix",
                                    min_year: int | None = None, max_year: int | None = None, min_rating: float | None = None) -> tuple[list[dict], bool]:
        started = time.perf_counter()
        version = await self._taste_version(user_id)
        pool_key = self._pool_key(user_id, target_type, min_year, max_year, min_rating, version)
        if not force_refresh:
            cached = await self.recs_pool_cache.get(pool_key)
            if cached and cursor < len(cached): return cached[cursor:cursor + 10], False
        genre_weights, top_genres, recent_liked_ids, blacklist, total_swipes, rows = await self._get_user_context(user_id)
        taste_loaded = time.perf_counter()
        movie_ratio = self._movie_ratio(rows)
        session_data = await self.session_cache.get(f"session_{user_id}") if self.session_cache else {}
        session_data = session_data or {}
        shown_ids = {tuple(item) for item in session_data.get("shown_ids", []) if isinstance(item, (list, tuple)) and len(item) == 2}
        effective_blacklist = blacklist | shown_ids
        profile_row = await self._load_taste_profile(user_id)
        if profile_row:
            profile = {field: profile_row.get(f"{field}_jsonb") or {} for field in PROFILE_FIELDS}
            profile.update({"movie_modifiers": profile_row.get("movie_modifiers_jsonb") or {}, "tv_modifiers": profile_row.get("tv_modifiers_jsonb") or {}})
        else:
            fallback = self._profile_from_rows(rows)
            profile = {field: fallback.get(field) or {} for field in PROFILE_FIELDS}
            profile.update({"movie_modifiers": fallback.get("movie_modifiers") or {}, "tv_modifiers": fallback.get("tv_modifiers") or {}})
        if total_swipes <= 0:
            novice_started = time.perf_counter()
            final_raw = await self._fetch_novice_hits(effective_blacklist, target_type, top_genres, min_year, max_year, min_rating, movie_ratio)
            logger.info("recommendation_timing user=%s taste_ms=%.1f retrieval_ms=%.1f total_ms=%.1f",
                        user_id, (taste_loaded - started) * 1000, (time.perf_counter() - novice_started) * 1000,
                        (time.perf_counter() - started) * 1000)
        else:
            candidates = await self._fetch_candidates_from_tmdb(top_genres, recent_liked_ids, effective_blacklist, target_type, min_year, max_year, min_rating)
            retrieved = time.perf_counter()
            candidates = await self._join_local_metadata(candidates)
            candidates = self._filter_recently_shown(candidates, shown_ids)
            metadata_joined = time.perf_counter()
            ranked = sorted(self._score_candidates(candidates, genre_weights, recent_liked_ids, session_data, profile, total_swipes), key=lambda item: item.get("final_score", 0), reverse=True)
            scored = time.perf_counter()
            final_raw = self._select_buckets(ranked, 10, total_swipes)
            bucketed = time.perf_counter()
            final_raw = self._apply_diversity_and_protect_top(final_raw, target_type, movie_ratio)
            reranked = time.perf_counter()
            logger.info("recommendation_timing user=%s taste_ms=%.1f retrieval_ms=%.1f metadata_ms=%.1f scoring_ms=%.1f bucket_ms=%.1f rerank_ms=%.1f total_ms=%.1f",
                        user_id, (taste_loaded - started) * 1000, (retrieved - taste_loaded) * 1000,
                        (metadata_joined - retrieved) * 1000, (scored - metadata_joined) * 1000,
                        (bucketed - scored) * 1000, (reranked - bucketed) * 1000, (reranked - started) * 1000)
        if not final_raw:
            if target_type == "mix":
                batches = await asyncio.gather(
                    self._discover_with_cascade(top_genres, effective_blacklist, "movie", min_year, max_year, min_rating),
                    self._discover_with_cascade(top_genres, effective_blacklist, "tv", min_year, max_year, min_rating),
                )
                final_raw = self._apply_diversity_and_protect_top(batches[0] + batches[1], "mix", movie_ratio)
            else:
                final_raw = await self._discover_with_cascade(top_genres, effective_blacklist, target_type, min_year, max_year, min_rating)
        metadata_keys = ("title", "name", "poster_path", "overview", "vote_average", "vote_count", "genre_ids",
                         "release_date", "first_air_date", "keywords", "directors", "production_countries", "origin_country")
        final_pool = []
        for movie in final_raw[:10]:
            if movie.get("id") is None:
                continue
            item = {"movie_id": movie["id"], "reason": movie.get("reason", "Рекомендация для вас"),
                    "reason_code": movie.get("reason_code", "fallback"), "bucket": movie.get("bucket", "core"),
                    "score_breakdown": movie.get("score_breakdown", {}),
                    "media_type": movie.get("media_type", "movie")}
            item.update({key: movie[key] for key in metadata_keys if movie.get(key) is not None})
            final_pool.append(item)
        await self.recs_pool_cache.put(pool_key, final_pool)
        if self.session_cache and final_pool:
            new_shown = list(dict.fromkeys(
                [tuple(item) for item in session_data.get("shown_ids", []) if isinstance(item, (list, tuple)) and len(item) == 2]
                + [(item["movie_id"], item.get("media_type") or "movie") for item in final_pool]
            ))[-100:]
            await self.session_cache.put(f"session_{user_id}", {**session_data, "shown_ids": new_shown})
        return final_pool, True
