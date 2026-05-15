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
        """
        Логарифмическое сглаживание (Log Normalization).
        Защищает от доминации одного жанра, если юзер лайкнул его 50 раз.
        """
        return math.log(1 + count)

    def _calculate_recency_bonus(self, release_year: str) -> float:
        """
        Плавное старение (Smooth Recency).
        Дает бонус свежим фильмам, который плавно тает с годами.
        """
        try:
            year = int(release_year[:4])
            current_year = datetime.now().year
            years_old = current_year - year
            # Бонус макс 2.0, каждый год отнимает 0.3. Если фильму больше 6-7 лет, бонус = 0.
            return max(0.0, 2.0 - (0.3 * years_old))
        except (ValueError, TypeError):
            return 0.0

    def _biased_shuffle(self, items: list[dict]) -> list[dict]:
        """
        Взвешенный шаффл (Biased Shuffle).
        Добавляет легкий шум (-0.5 до 0.5) к скору, чтобы перемешать фильмы 
        со схожим рейтингом, но не утопить реальные шедевры.
        """
        for item in items:
            # Предполагаем, что у кандидата уже посчитан 'final_score'
            score = item.get('final_score', 0)
            item['shuffle_score'] = score + random.uniform(-0.5, 0.5)
            
        return sorted(items, key=lambda x: x.get('shuffle_score', 0), reverse=True)

    def _apply_diversity_and_protect_top(self, ranked_candidates: list[dict]) -> list[dict]:
        """
        Защита ТОП-5 и разбавка остальных (Top-5 Protection + Diversity).
        """
        if not ranked_candidates:
            return []

        # ТОП-5 отдаем как есть (Абсолютные хиты)
        top_5 = ranked_candidates[:5]
        
        # Остальное слегка перемешиваем
        rest = ranked_candidates[5:]
        if rest:
            rest = self._biased_shuffle(rest)

        # Здесь позже можно добавить логику "не больше 2 одинаковых жанров подряд"
        return top_5 + rest

# Создаем глобальный экземпляр (экспортируем его для api.py)
# Но инициализировать будем чуть позже, когда свяжем с config.py
    async def _get_user_context(self, user_id: int):
        """
        Собирает профиль: взвешенные сигналы (Лайк=1.0, Ватчлист=0.35, Архив=-0.15)
        """
        liked_movies = await self.db.get_user_media_by_status(user_id, 'liked')
        watchlist_movies = await self.db.get_user_media_by_status(user_id, 'watchlist')
        archived = await self.db.get_user_media_by_status(user_id, 'archive')
        
        genre_scores = {} 
        blacklist = set()
        recent_liked_ids = []

        # 1. ЛАЙКИ (СИЛЬНЫЙ СИГНАЛ: +1.0)
        for item in liked_movies:
            movie_id = item.get('movie_id')
            blacklist.add(movie_id)
            recent_liked_ids.append({"id": movie_id, "type": item.get('media_type', 'movie')})
            
            genres = (item.get('movies') or {}).get('genres_array') or []
            if isinstance(genres, list):
                for g_id in genres:
                    genre_scores[g_id] = genre_scores.get(g_id, 0.0) + 1.0

        # 2. ВОТЧЛИСТ (СЛАБЫЙ СИГНАЛ: +0.35)
        for item in watchlist_movies:
            movie_id = item.get('movie_id')
            blacklist.add(movie_id) 
            
            genres = (item.get('movies') or {}).get('genres_array') or []
            if isinstance(genres, list):
                for g_id in genres:
                    genre_scores[g_id] = genre_scores.get(g_id, 0.0) + 0.35

        # 3. АРХИВ (ПЕССИМИЗАЦИЯ: -0.15)
        for item in archived:
            movie_id = item.get('movie_id')
            blacklist.add(movie_id)
            
            genres = (item.get('movies') or {}).get('genres_array') or []
            if isinstance(genres, list):
                for g_id in genres:
                    current = genre_scores.get(g_id, 0.0)
                    genre_scores[g_id] = max(0.0, current - 0.15) # Не даем уйти ниже нуля

        # Превращаем финальные скоры в логарифмические веса
        genre_weights = {g_id: self._calculate_genre_weight(score) 
                         for g_id, score in genre_scores.items() if score > 0}

        # Якоря берем ТОЛЬКО из лайков!
        recent_liked_ids = recent_liked_ids[-3:] if recent_liked_ids else []
        top_genres = sorted(genre_weights.keys(), key=lambda k: genre_weights[k], reverse=True)[:3]
        total_swipes = len(liked_movies) + len(archived) + len(watchlist_movies)

        return genre_weights, top_genres, recent_liked_ids, blacklist, total_swipes

    async def _fetch_candidates_from_tmdb(self, top_genres: list, recent_liked_ids: list, blacklist: set) -> list[dict]:
        """
        Генерирует сырой пул кандидатов из 3 источников (TMDB).
        """
        raw_candidates = {} 

        base_filters = {
            "vote_count.gte": 500,
            "vote_average.gte": 6.5,
        }

        # Вектор А: Широкая выборка по любимым жанрам
        if top_genres:
            genre_movies = await self.tmdb.discover_with_filters(with_genres=top_genres, **base_filters)
            for m in (genre_movies or {}).get('results', []) or []:
                m_id = m.get("id")
                # Тут проверка была:
                if m_id is None or m_id in raw_candidates or m_id in blacklist:
                    continue
                m["_source_reason"] = "В твоих любимых жанрах"
                raw_candidates[m_id] = m

        # Вектор Б: Похожее на последние лайки
        for m_info in recent_liked_ids:
            m_id = m_info["id"]
            m_type = m_info["type"]
            try:
                similar_movies = await self.tmdb.get_recommendations(movie_id=m_id, media_type=m_type)
                if not similar_movies or not similar_movies.get("results"):
                    continue
                for m in similar_movies.get('results', [])[:10]:
                    m_id_similar = m.get("id")
                    
                    # --- ИСПРАВЛЕНИЕ: Добавили проверку на blacklist ---
                    if m_id_similar is None or m_id_similar in raw_candidates or m_id_similar in blacklist:
                        continue
                        
                    if m.get("vote_count", 0) < base_filters["vote_count.gte"] or m.get("vote_average", 0) < base_filters["vote_average.gte"]:
                        continue
                    
                    m["_source_reason"] = "Похоже на то, что ты оценил"
                    raw_candidates[m_id_similar] = m
            except Exception as e:
                logger.error(f"Ошибка при получении рекомендаций для {m_type} {m_id}: {e}")
                continue

        # Вектор В: Свежие тренды
        current_year = datetime.now().year
        trending = await self.tmdb.discover_with_filters(year_from=current_year - 2, year_to=current_year, **base_filters)
        
        for m in (trending or {}).get('results', []) or []:
            m_id_trending = m.get("id")
            
            # --- ИСПРАВЛЕНИЕ: Добавили проверку на blacklist ---
            if m_id_trending is None or m_id_trending in raw_candidates or m_id_trending in blacklist:
                continue
                
            release_date = m.get('release_date') or m.get('first_air_date') or ''
            if release_date.startswith(str(current_year)):
                m["_source_reason"] = "Свежая новинка"
            else:
                m["_source_reason"] = "Громкий хит последних лет"
                
            raw_candidates[m_id_trending] = m

        return list(raw_candidates.values())
    
    def _score_candidates(self, candidates: list[dict], genre_weights: dict, recent_liked_ids: list, session_data: dict) -> list[dict]:
        """
        Прогоняет сырых кандидатов через аддитивную математику: Базовый вес + TMDB + Session Bonus/Penalty.
        """
        scored_candidates = []
        recent_skipped_genres = session_data.get('skipped_genres', [])

        for movie in candidates:
            # 1. Base Score (Веса жанров + нормализованный рейтинг TMDB)
            movie_genres = movie.get('genre_ids', [])
            w_genre_sum = sum(genre_weights.get(g, 0.0) for g in movie_genres)
            
            tmdb_score = movie.get('vote_average', 0) / 10.0
            base_score = w_genre_sum + (tmdb_score * 2)

            # 2. Recency Bonus (Плавное старение)
            release_date = movie.get('release_date', '')
            recency_bonus = self._calculate_recency_bonus(release_date)

            # 3. Session Modifiers
            session_penalty = 0.0
            
            # Штраф за скипнутые в текущей сессии жанры (порог: если скипнул жанр >= 3 раз)
            for g in movie_genres:
                if recent_skipped_genres.count(g) >= 3:
                    session_penalty += 0.8
                    break # Одного штрафа на фильм достаточно

            final_score = base_score + recency_bonus - session_penalty
            
            # 4. Explainability (Причина для UX)
            reason = movie.get('_source_reason', 'Рекомендация для вас')
            if tmdb_score > 0.8 and w_genre_sum > 1.0:
                reason = "Признанный шедевр в твоем вкусе"

            movie['final_score'] = final_score
            movie['reason'] = reason
            scored_candidates.append(movie)

        return scored_candidates

    async def get_next_movies(self, user_id: int, cursor: int = 0, force_refresh: bool = False) -> list[dict]:
        """
        Главный метод (входная точка для API). 
        Отдает 10 фильмов, используя кэш или генерируя новый пул.
        """
        pool_key = f"user_recs_pool_{user_id}"
        
        # 1. Проверяем наличие пула в кэше, ТОЛЬКО ЕСЛИ не запрошен force_refresh
        if not force_refresh:
            cached_pool = await self.recs_pool_cache.get(pool_key)
            
            # Если пул есть и мы не дошли до конца очереди
            if cached_pool and cursor < len(cached_pool):
                return cached_pool[cursor : cursor + 10], False

        # 2. Если force_refresh=True или кэша нет — запускаем всю машину сборки!
        genre_weights, top_genres, recent_liked_ids, blacklist, total_swipes = await self._get_user_context(user_id)

        if total_swipes < 20:
            # Режим новичка: отдаем абсолютные легенды кинематографа
            hits = await self.tmdb.discover_with_filters(
                **{
                    "vote_average.gte": 7.8, # Только элита (рейтинг от 7.8)
                    "vote_count.gte": 10000  # Минимум 10 ТЫСЯЧ голосов (отсекает локальный артхаус и порно)
                },
                sort_by="vote_count.desc",   # Сортировка по популярности ЗА ВСЕ ВРЕМЯ
                without_genres="99",         # Убиваем документалки
                page=random.randint(1, 2)    # Берем только топ-40 самых известных фильмов мира
            )
            raw_candidates = (hits or {}).get('results', []) or []
            for m in raw_candidates:
                m['reason'] = "Мировой хит (Специально для новичков)"
                m['final_score'] = m.get('vote_average', 0)

            clean_candidates = [m for m in raw_candidates if m['id'] not in blacklist]
            final_pool_raw = clean_candidates[:10]
        else:
            # Собираем УЖЕ ЧИСТЫХ кандидатов, прокинув blacklist
            clean_candidates = await self._fetch_candidates_from_tmdb(top_genres, recent_liked_ids, blacklist)

            # Достаем сессионный контекст (историю текущих свайпов)
            session_data = await self.session_cache.get(f"session_{user_id}") or {}

            # 3. Скоринг
            scored = self._score_candidates(clean_candidates, genre_weights, recent_liked_ids, session_data)

            # Ранжируем строго по убыванию баллов
            ranked = sorted(scored, key=lambda x: x.get('final_score', 0), reverse=True)

            # 4. Применяем защиту ТОП-5 и разбавочный шаффл
            final_pool_raw = self._apply_diversity_and_protect_top(ranked)

        # АДАПТАЦИЯ ДЛЯ ФРОНТЕНДА: TMDB отдает 'id', а Lovable ждет 'movie_id'
        # --- НОВАЯ МАГИЯ: ДОСТАЕМ АКТЕРОВ ИЗ ЛОКАЛЬНОЙ БАЗЫ ОДНИМ ЗАПРОСОМ ---
        movie_ids = [m.get("id") for m in final_pool_raw if m.get("id")]
        local_movies_data = {}
        if movie_ids:
            try:
                # Идем в базу и просим инфу сразу для всей пачки
                query = self.db._client.table("movies").select("id, actors, directors, runtime_mins").in_("id", movie_ids)
                response = await self.db._execute(query)
                if response.data:
                    for row in response.data:
                        local_movies_data[row["id"]] = row
            except Exception as e:
                logger.error(f"Ошибка при массовом получении актеров: {e}")

        # АДАПТАЦИЯ ДЛЯ ФРОНТЕНДА
        final_pool = []
        from utils.genres import TMDB_GENRES
        
        for m in final_pool_raw:
            m_id = m.get("id")
            release_date = m.get("release_date") or m.get("first_air_date") or ""
            year = release_date[:4] if len(release_date) >= 4 else "????"
            g_ids = m.get("genre_ids", []) or []
            genre_names = [TMDB_GENRES.get(gid, "Жанр") for gid in g_ids[:2]]
            
            # Подтягиваем локальные данные, если они нашлись
            local_data = local_movies_data.get(m_id, {})

            final_pool.append({
                "movie_id": m_id,
                "title": m.get("title") or m.get("name", "Без названия"),
                "poster_path": m.get("poster_path", ""),
                "rating": round(m.get("vote_average", 0.0) or 0.0, 1),
                "year": year,
                "genre_names": genre_names,
                "reason": m.get("reason", ""),
                "overview": m.get("overview", ""),
                "media_type": m.get("media_type", "movie"),
                "genre_ids": g_ids,
                # НОВЫЕ ПОЛЯ ДЛЯ КАРТОЧКИ (ФРОНТЕНДА)
                "actors": local_data.get("actors") or "",
                "directors": local_data.get("directors") or "",
                "runtime_mins": local_data.get("runtime_mins") or None
            })

        # 5. Сохраняем готовую очередь в кэш и отдаем первые 10 карточек
        await self.recs_pool_cache.put(pool_key, final_pool)
        return final_pool[:10], True
