import math
import random
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RecommendationService:
    def __init__(self, db, tmdb, session_cache, recs_pool_cache):
        self.db = db
        self.tmdb = tmdb
        self.session_cache = session_cache
        self.recs_pool_cache = recs_pool_cache

    def _calculate_genre_weight(self, count: int) -> float:
        return math.log(1 + count)

    def _calculate_recency_bonus(self, release_year: str) -> float:
        try:
            year = int(release_year[:4])
            current_year = datetime.now().year
            years_old = current_year - year
            return max(0.0, 2.0 - (0.3 * years_old))
        except (ValueError, TypeError):
            return 0.0

    def _biased_shuffle(self, items: list[dict]) -> list[dict]:
        for item in items:
            score = item.get('final_score', 0)
            item['shuffle_score'] = score + random.uniform(-0.5, 0.5)
        return sorted(items, key=lambda x: x.get('shuffle_score', 0), reverse=True)

    def _apply_diversity_and_protect_top(self, ranked_candidates: list[dict]) -> list[dict]:
        if not ranked_candidates:
            return []
        top_5 = ranked_candidates[:5]
        rest = ranked_candidates[5:]
        if rest:
            rest = self._biased_shuffle(rest)
        return top_5 + rest

    async def _get_user_context(self, user_id: int):
        try:
            response = await self.db._execute(
                self.db._client.table("user_movies")
                .select("movie_id, status, media_type, movies(*)")
                .eq("user_id", user_id)
            )
            rows = response.data if response and hasattr(response, 'data') else []
        except Exception as e:
            logger.error(f"Context error: {e}")
            rows = []
        
        genre_scores = {} 
        blacklist = set()
        recent_liked_ids = []

        for item in rows:
            movie_id = item.get('movie_id')
            status = item.get('status')
            media_type = item.get('media_type', 'movie')
            movies_data = item.get('movies') or {}
            
            genres = movies_data.get('genre_ids') or movies_data.get('genres_array') or movies_data.get('genres') or []
            
            blacklist.add(movie_id)

            if status == 'liked':
                recent_liked_ids.append({"id": movie_id, "type": media_type})
                if isinstance(genres, list):
                    for g_id in genres:
                        genre_scores[g_id] = genre_scores.get(g_id, 0.0) + 1.0
                        
            elif status == 'watchlist':
                if isinstance(genres, list):
                    for g_id in genres:
                        genre_scores[g_id] = genre_scores.get(g_id, 0.0) + 0.35
                        
            elif status == 'archive':
                if isinstance(genres, list):
                    for g_id in genres:
                        current = genre_scores.get(g_id, 0.0)
                        genre_scores[g_id] = max(0.0, current - 0.15)

        genre_weights = {g_id: self._calculate_genre_weight(score) 
                         for g_id, score in genre_scores.items() if score > 0}

        recent_liked_ids = recent_liked_ids[-3:] if recent_liked_ids else []
        top_genres = sorted(genre_weights.keys(), key=lambda k: genre_weights[k], reverse=True)[:3]
        total_swipes = len(rows)

        return genre_weights, top_genres, recent_liked_ids, blacklist, total_swipes

    def _pick_media_type(self) -> str:
        return "tv" if random.random() < 0.27 else "movie"

    def _filter_blacklist(self, results: list[dict], blacklist: set) -> list[dict]:
        return [m for m in results if m.get("id") is not None and m.get("id") not in blacklist]

    def _merge_candidates(self, raw_candidates: dict, items: list[dict], reason: str | None = None) -> None:
        for m in items:
            m_id = m.get("id")
            if m_id is None:
                continue
            media_type = m.get("media_type", "movie")
            key = (m_id, media_type)
            if key in raw_candidates:
                continue
            if reason:
                m["_source_reason"] = reason
            raw_candidates[key] = m

    async def _discover_with_cascade(
        self,
        top_genres: list,
        blacklist: set,
        media_type: str | None = None,
    ) -> list[dict]:
        media_type = media_type or self._pick_media_type()
        current_year = datetime.now().year
        strict_filters = {"vote_count.gte": 500, "vote_average.gte": 6.5}

        # Шаг 1 (строгий): пересечение любимых жанров
        if top_genres:
            strict = await self.tmdb.discover_with_filters(
                with_genres=top_genres,
                year_from=current_year - 5,
                year_to=current_year,
                media_type=media_type,
                page=random.randint(1, 10),
                **strict_filters,
            )
            filtered = self._filter_blacklist((strict or {}).get("results", []) or [], blacklist)
            if filtered:
                for m in filtered:
                    m["_source_reason"] = "В твоих любимых жанрах"
                return filtered

        # Шаг 2 (широкий): один случайный жанр, расширенный диапазон годов
        if top_genres:
            wide = await self.tmdb.discover_with_filters(
                with_genres=[random.choice(top_genres)],
                year_from=current_year - 15,
                year_to=current_year,
                media_type=media_type,
                page=random.randint(1, 15),
                **{"vote_count.gte": 300, "vote_average.gte": 6.0},
            )
            filtered = self._filter_blacklist((wide or {}).get("results", []) or [], blacklist)
            if filtered:
                for m in filtered:
                    m["_source_reason"] = "В твоей зоне интересов"
                return filtered

        # Шаг 3 (спасательный): популярные тайтлы без учёта вкусов
        for attempt_media in (media_type, "movie" if media_type == "tv" else "tv"):
            for _ in range(3):
                lifeboat = await self.tmdb.discover_with_filters(
                    media_type=attempt_media,
                    sort_by="popularity.desc",
                    page=random.randint(1, 20),
                    **{"vote_count.gte": 500},
                )
                filtered = self._filter_blacklist((lifeboat or {}).get("results", []) or [], blacklist)
                if filtered:
                    for m in filtered:
                        m["_source_reason"] = "Популярное прямо сейчас"
                    return filtered
        return []

    async def _fetch_candidates_from_tmdb(self, top_genres: list, recent_liked_ids: list, blacklist: set) -> list[dict]:
        raw_candidates: dict[tuple, dict] = {}
        base_filters = {"vote_count.gte": 500, "vote_average.gte": 6.5}
        current_year = datetime.now().year

        genre_items = await self._discover_with_cascade(top_genres, blacklist)
        self._merge_candidates(raw_candidates, genre_items)

        for m_info in recent_liked_ids:
            m_id = m_info["id"]
            m_type = m_info["type"]
            try:
                similar_movies = await self.tmdb.get_recommendations(movie_id=m_id, media_type=m_type)
                similar_filtered = []
                for m in (similar_movies or {}).get("results", [])[:10]:
                    if m.get("vote_count", 0) < base_filters["vote_count.gte"] or m.get("vote_average", 0) < base_filters["vote_average.gte"]:
                        continue
                    m["media_type"] = m_type
                    if m.get("id") not in blacklist:
                        similar_filtered.append(m)
                self._merge_candidates(raw_candidates, similar_filtered, "Похоже на то, что ты оценил")
            except Exception as e:
                logger.error(f"Ошибка при получении рекомендаций для {m_type} {m_id}: {e}")

        trending_media = self._pick_media_type()
        trending = await self.tmdb.discover_with_filters(
            year_from=current_year - 2,
            year_to=current_year,
            media_type=trending_media,
            page=random.randint(1, 5),
            **base_filters,
        )
        trending_filtered = self._filter_blacklist((trending or {}).get("results", []) or [], blacklist)
        for m in trending_filtered:
            release_date = m.get("release_date") or m.get("first_air_date") or ""
            m["_source_reason"] = "Свежая новинка" if release_date.startswith(str(current_year)) else "Громкий хит последних лет"
        self._merge_candidates(raw_candidates, trending_filtered)

        if not raw_candidates:
            fallback_media = self._pick_media_type()
            fallback_items = await self._discover_with_cascade([], blacklist, media_type=fallback_media)
            self._merge_candidates(raw_candidates, fallback_items)

        return list(raw_candidates.values())
    
    def _score_candidates(self, candidates: list[dict], genre_weights: dict, recent_liked_ids: list, session_data: dict) -> list[dict]:
        scored_candidates = []
        recent_skipped_genres = session_data.get('skipped_genres', [])

        for movie in candidates:
            movie_genres = movie.get('genre_ids', [])
            w_genre_sum = sum(genre_weights.get(g, 0.0) for g in movie_genres)
            
            tmdb_score = movie.get('vote_average', 0) / 10.0
            base_score = w_genre_sum + (tmdb_score * 2)

            release_date = movie.get('release_date') or movie.get('first_air_date') or ''
            recency_bonus = self._calculate_recency_bonus(release_date)

            session_penalty = 0.0
            for g in movie_genres:
                if recent_skipped_genres.count(g) >= 3:
                    session_penalty += 0.8
                    break

            final_score = base_score + recency_bonus - session_penalty
            
            reason = movie.get('_source_reason', 'Рекомендация для вас')
            if tmdb_score > 0.8 and w_genre_sum > 1.0:
                reason = "Признанный шедевр в твоем вкусе"

            movie['final_score'] = final_score
            movie['reason'] = reason
            scored_candidates.append(movie)

        return scored_candidates

    async def get_next_movies(self, user_id: int, cursor: int = 0, force_refresh: bool = False) -> list[dict]:
        pool_key = f"user_recs_pool_{user_id}"
        
        if not force_refresh:
            cached_pool = await self.recs_pool_cache.get(pool_key)
            if cached_pool and cursor < len(cached_pool):
                return cached_pool[cursor : cursor + 10], False

        genre_weights, top_genres, recent_liked_ids, blacklist, total_swipes = await self._get_user_context(user_id)

        if total_swipes < 20:
            novice_media = self._pick_media_type()
            hits = await self.tmdb.discover_with_filters(
                media_type=novice_media,
                **{"vote_average.gte": 7.8, "vote_count.gte": 10000},
                sort_by="vote_count.desc",
                without_genres="99",
                page=random.randint(1, 2),
            )
            raw_candidates = self._filter_blacklist((hits or {}).get("results", []) or [], blacklist)
            if not raw_candidates:
                raw_candidates = await self._discover_with_cascade(top_genres, blacklist, media_type=novice_media)
            for m in raw_candidates:
                m["reason"] = "Мировой хит (Специально для новичков)"
                m["final_score"] = m.get("vote_average", 0)
            final_pool_raw = raw_candidates[:10]
        else:
            clean_candidates = await self._fetch_candidates_from_tmdb(top_genres, recent_liked_ids, blacklist)
            session_data = await self.session_cache.get(f"session_{user_id}") or {}
            scored = self._score_candidates(clean_candidates, genre_weights, recent_liked_ids, session_data)
            ranked = sorted(scored, key=lambda x: x.get('final_score', 0), reverse=True)
            final_pool_raw = self._apply_diversity_and_protect_top(ranked)

        if not final_pool_raw:
            emergency_media = self._pick_media_type()
            emergency = await self._discover_with_cascade(top_genres, blacklist, media_type=emergency_media)
            final_pool_raw = emergency[:10]

        final_pool = []
        for m in final_pool_raw:
            final_pool.append({
                "movie_id": m.get("id"),
                "reason": m.get("reason", m.get("reason_text", "Рекомендация для вас")),
                "media_type": m.get("media_type", "movie")
            })

        await self.recs_pool_cache.put(pool_key, final_pool)
        return final_pool[:10], True