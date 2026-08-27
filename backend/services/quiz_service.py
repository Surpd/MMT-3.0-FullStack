from __future__ import annotations

import hashlib
import asyncio
import logging
import random
import secrets
from dataclasses import dataclass
from datetime import date
from time import perf_counter
from typing import Any

from services.stats_service import stats_service

LIBRARY_MINIMUM = 20
SESSION_SIZES = {"cinema": 10, "library": 10, "daily": 7}
DIFFICULTY_MULTIPLIERS = {"easy": 1.0, "medium": 1.25, "hard": 1.5}
GLOBAL_POOL_LIMIT = 600
LIBRARY_SAMPLE_LIMIT = 100
GLOBAL_POOL_TTL_SEC = 20 * 60
LIBRARY_POOL_TTL_SEC = 15 * 60
DAILY_QUESTIONS_TTL_SEC = 48 * 60 * 60

logger = logging.getLogger(__name__)


def _title(row: dict[str, Any]) -> str:
    return str(row.get("title") or row.get("name") or "").strip()


def _media_type(row: dict[str, Any]) -> str:
    return row.get("media_type") if row.get("media_type") in {"movie", "tv"} else "movie"


def _year(row: dict[str, Any]) -> int | None:
    value = row.get("year") or row.get("release_date") or row.get("first_air_date") or ""
    try:
        parsed = int(str(value)[:4])
    except (TypeError, ValueError):
        return None
    return parsed if 1888 <= parsed <= date.today().year + 2 else None


def _list_value(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("name")
        if isinstance(item, str) and item.strip() and item.strip() not in result:
            result.append(item.strip())
    return result


def _rating(row: dict[str, Any]) -> Any:
    return row.get("user_rating") if row.get("user_rating") is not None else row.get("rating")


def _poster(row: dict[str, Any]) -> str:
    backdrop = row.get("backdrop_url") or row.get("backdrop_path") or row.get("still_url") or row.get("still_path")
    value = backdrop or row.get("poster_url") or row.get("poster_path") or ""
    if not isinstance(value, str):
        return ""
    return value if value.startswith("http") else f"https://image.tmdb.org/t/p/{'w780' if backdrop else 'w500'}{value}" if value else ""


def _visual(row: dict[str, Any]) -> str:
    value = row.get("backdrop_url") or row.get("backdrop_path") or row.get("still_url") or row.get("still_path") or ""
    if not isinstance(value, str):
        return ""
    return value if value.startswith("http") else f"https://image.tmdb.org/t/p/w780{value}" if value else ""


def _key(row: dict[str, Any]) -> tuple[int, str]:
    try:
        movie_id = int(row.get("id") or row.get("movie_id"))
    except (TypeError, ValueError):
        movie_id = 0
    return movie_id, _media_type(row)


def _recognizable(row: dict[str, Any]) -> bool:
    if not _title(row) or not _key(row)[0]:
        return False
    vote_count = row.get("tmdb_vote_count")
    if vote_count is None:
        vote_count = row.get("vote_count")
    try:
        if vote_count is not None and int(vote_count) < 30:
            return False
    except (TypeError, ValueError):
        pass
    return True


@dataclass(frozen=True, slots=True)
class QuizQuestion:
    question_id: str
    question_type: str
    difficulty: str
    prompt: str
    options: tuple[str, ...]
    correct_answer: str
    movie_id: int
    media_type: str
    poster_url: str = ""
    personal: bool = False

    def public(self, index: int) -> dict[str, Any]:
        return {"id": self.question_id, "question": self.prompt, "options": list(self.options), "difficulty": self.difficulty, "type": self.question_type, "movie_id": self.movie_id, "media_type": self.media_type, "poster_url": self.poster_url, "personal": self.personal, "index": index}

    def private(self) -> dict[str, Any]:
        return {**self.public(0), "correct_answer": self.correct_answer}


def _question_id(question_type: str, movie_id: int, media_type: str, options: list[str]) -> str:
    return hashlib.sha1("|".join([question_type, str(movie_id), media_type, *options]).encode("utf-8")).hexdigest()[:20]


@dataclass(slots=True)
class QuizCandidatePool:
    """Bounded, indexed runtime input for one or more quiz sessions."""

    rows: list[dict[str, Any]]
    library_rows: list[dict[str, Any]]
    indexes: dict[str, list[dict[str, Any]]]
    neighbors: dict[tuple[int, str], list[dict[str, Any]]]
    person_counts: dict[str, int]
    library_keys: set[tuple[int, str]]
    library_count: int | None = None


def build_candidate_pool(
    rows: list[dict[str, Any]],
    library_rows: list[dict[str, Any]] | None = None,
    library_count: int | None = None,
) -> QuizCandidatePool:
    """Prepare capabilities and candidate indexes once for a bounded pool."""
    targets = [row for row in rows if isinstance(row, dict) and _recognizable(row)]
    library = [row for row in (library_rows or []) if isinstance(row, dict) and _key(row)[0]]
    library_keys = {_key(row) for row in library}
    neighbors: dict[tuple[int, str], list[dict[str, Any]]] = {}
    person_counts: dict[str, int] = {}
    for row in targets:
        people = set(_list_value(row.get("actors") or row.get("cast")) + _list_value(row.get("directors")))
        for person in people:
            person_counts[person] = person_counts.get(person, 0) + 1
    for target in targets:
        target_year = _year(target) or 2000
        candidates = [
            row for row in targets
            if _key(row) != _key(target) and _media_type(row) == _media_type(target)
        ]
        candidates.sort(key=lambda row: abs((_year(row) or target_year) - target_year))
        neighbors[_key(target)] = candidates[:24]

    rated_library = [row for row in library if _rating(row) is not None]
    indexes: dict[str, list[dict[str, Any]]] = {
        "description_title": [row for row in targets if isinstance(row.get("overview"), str) and len(row["overview"].strip()) >= 40],
        "director": [row for row in targets if _list_value(row.get("directors"))],
        "cast": [row for row in targets if _list_value(row.get("actors") or row.get("cast"))],
        "filmography": [row for row in targets if any(person_counts.get(person, 0) == 1 for person in _list_value(row.get("actors") or row.get("directors")))],
        "release_year": [row for row in targets if _year(row) is not None],
        "chronology": [row for row in targets if _year(row) is not None],
        "visual_candidates": [row for row in targets if _visual(row)],
        "visual_title": [row for row in targets if _visual(row)],
        "in_library": list(library),
        "not_in_library": [row for row in targets if _key(row) not in library_keys],
        "my_rating": rated_library if len(rated_library) >= 3 else [],
        "higher_rated": [row for row in rated_library if len(rated_library) >= 2],
    }
    return QuizCandidatePool(targets, library, indexes, neighbors, person_counts, library_keys, library_count)


class QuestionEngine:
    """Small, testable generators over one already-loaded catalog."""

    def __init__(self, pool: QuizCandidatePool | None = None) -> None:
        self.pool = pool

    def _distractors(self, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
        if self.pool is not None:
            candidates = list(self.pool.neighbors.get(_key(target), []))
            rng.shuffle(candidates)
            return candidates
        target_year = _year(target)
        candidates = [row for row in catalog if _key(row) != _key(target) and _media_type(row) == _media_type(target) and _title(row)]
        rng.shuffle(candidates)
        candidates.sort(key=lambda row: abs((_year(row) or target_year or 2000) - (target_year or 2000)))
        return candidates

    def _make(self, question_type: str, difficulty: str, prompt: str, correct: str, options: list[str], target: dict[str, Any], rng: random.Random, personal: bool = False) -> QuizQuestion | None:
        unique = list(dict.fromkeys(option.strip() for option in options if isinstance(option, str) and option.strip()))
        if not correct or correct not in unique or len(unique) < 2:
            return None
        rng.shuffle(unique)
        return QuizQuestion(_question_id(question_type, _key(target)[0], _media_type(target), unique), question_type, difficulty, prompt, tuple(unique), correct, _key(target)[0], _media_type(target), _poster(target), personal)

    def poster_title(self, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        correct = _title(target)
        visual = _visual(target)
        if not visual or not correct:
            return None
        question = self._make("visual_title", "easy", "Как называется это произведение?", correct, [correct, *[_title(row) for row in self._distractors(target, catalog, rng)]][:4], target, rng)
        if question:
            return QuizQuestion(question.question_id, question.question_type, question.difficulty, question.prompt, question.options, question.correct_answer, question.movie_id, question.media_type, visual, question.personal)
        return None

    def visual_title(self, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        return self.poster_title(target, catalog, rng)

    def description_title(self, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        overview, correct = target.get("overview"), _title(target)
        if not isinstance(overview, str) or len(overview.strip()) < 40 or not correct:
            return None
        return self._make("description_title", "medium", overview.strip(), correct, [correct, *[_title(row) for row in self._distractors(target, catalog, rng)]][:4], target, rng)

    def director(self, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        directors = _list_value(target.get("directors"))
        if not directors:
            return None
        correct, wrong = directors[0], []
        for row in self._distractors(target, catalog, rng):
            names = _list_value(row.get("directors"))
            if names and names[0] != correct and names[0] not in wrong:
                wrong.append(names[0])
            if len(wrong) == 3:
                break
        return self._make("director", "medium", f"Кто работал режиссёром над «{_title(target)}»?", correct, [correct, *wrong], target, rng)

    def cast(self, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        actors = _list_value(target.get("actors") or target.get("cast"))
        if not actors:
            return None
        correct, wrong = actors[0], []
        for row in self._distractors(target, catalog, rng):
            names = [name for name in _list_value(row.get("actors") or row.get("cast")) if name not in actors and name not in wrong]
            if names:
                wrong.append(names[0])
            if len(wrong) == 3:
                break
        return self._make("cast", "medium", f"Кто указан в актёрском составе «{_title(target)}»?", correct, [correct, *wrong], target, rng)

    def filmography(self, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        people = _list_value(target.get("actors") or target.get("directors"))
        person = next((name for name in people if (self.pool.person_counts.get(name, 0) if self.pool else sum(name in _list_value(row.get("actors") or row.get("directors")) for row in catalog)) == 1), None)
        if not person:
            return None
        wrong = [_title(row) for row in self._distractors(target, catalog, rng) if person not in _list_value(row.get("actors") or row.get("directors"))]
        return self._make("filmography", "hard", f"С каким произведением связан {person}?", _title(target), [_title(target), *wrong][:4], target, rng)

    def release_year(self, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        year = _year(target)
        if year is None:
            return None
        wrong = [str(_year(row)) for row in self._distractors(target, catalog, rng) if _year(row) is not None and _year(row) != year]
        return self._make("release_year", "easy", f"В каком году вышло «{_title(target)}»?", str(year), [str(year), *wrong][:4], target, rng)

    def chronology(self, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        target_year = _year(target)
        other = next((row for row in self._distractors(target, catalog, rng) if _year(row) is not None and _year(row) != target_year), None)
        if target_year is None or other is None:
            return None
        other_year = _year(other)
        correct = _title(target) if target_year < other_year else _title(other)
        return self._make("chronology", "hard", f"Что вышло раньше: «{_title(target)}» или «{_title(other)}»?", correct, [_title(target), _title(other)], target, rng)

    def in_library(self, target: dict[str, Any], library: list[dict[str, Any]], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        library_keys = {_key(row) for row in library}
        if _key(target) not in library_keys:
            return None
        wrong = [_title(row) for row in self._distractors(target, catalog, rng) if _key(row) not in library_keys]
        return self._make("in_library", "easy", "Какое произведение есть в вашей библиотеке?", _title(target), [_title(target), *wrong][:4], target, rng, personal=True)

    def not_in_library(self, target: dict[str, Any], library: list[dict[str, Any]], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        library_keys = {_key(row) for row in library}
        if _key(target) in library_keys:
            return None
        wrong = [_title(row) for row in library if _title(row) and _key(row) != _key(target)]
        return self._make("not_in_library", "medium", "Какого произведения нет в вашей библиотеке?", _title(target), [_title(target), *wrong][:4], target, rng, personal=True)

    def my_rating(self, target: dict[str, Any], library: list[dict[str, Any]], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        rating = _rating(target)
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            return None
        rated_count = sum(_rating(row) is not None for row in library)
        if rating not in range(1, 6) or rated_count < 3:
            return None
        return self._make("my_rating", "medium", f"Какую оценку вы поставили «{_title(target)}»?", str(rating), [str(value) for value in range(1, 6)], target, rng, personal=True)

    def higher_rated(self, target: dict[str, Any], library: list[dict[str, Any]], catalog: list[dict[str, Any]], rng: random.Random) -> QuizQuestion | None:
        rated = [row for row in library if _rating(row) is not None]
        pair = next(((left, right) for left in rated for right in rated if _key(left) != _key(right) and _rating(left) != _rating(right)), None)
        if not pair:
            return None
        left, right = pair
        correct = _title(left) if _rating(left) > _rating(right) else _title(right)
        return self._make("higher_rated", "hard", "Какое произведение вы оценили выше?", correct, [_title(left), _title(right)], target, rng, personal=True)

    def generate(self, question_type: str, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random, library: list[dict[str, Any]] | None = None) -> QuizQuestion | None:
        method = getattr(self, question_type, None)
        if not method:
            return None
        return method(target, library or [], catalog, rng) if question_type in {"in_library", "not_in_library", "my_rating", "higher_rated"} else method(target, catalog, rng)


def compose_questions(catalog: list[dict[str, Any]] | QuizCandidatePool, mode: str = "cinema", library: list[dict[str, Any]] | None = None, count: int | None = None, seed: int | None = None) -> list[QuizQuestion]:
    pool = catalog if isinstance(catalog, QuizCandidatePool) else build_candidate_pool(catalog, library)
    engine, rng = QuestionEngine(pool), random.Random(seed)
    count = count or SESSION_SIZES.get(mode, 10)
    personal_types = ["in_library", "not_in_library", "my_rating", "higher_rated"]
    general_types = ["description_title", "director", "cast", "filmography", "release_year", "chronology"]
    targets, library = pool.rows, pool.library_rows if library is None else library
    if mode == "library":
        type_slots = [personal_types[i % len(personal_types)] for i in range(min(6, count))] + [general_types[i % len(general_types)] for i in range(max(0, count - 6))]
    elif mode == "daily":
        type_slots = ["release_year", "description_title", "director", "cast", "chronology", "filmography", "release_year"]
    else:
        type_slots = ["release_year", "description_title", "director", "cast", "description_title", "filmography", "release_year", "chronology", "cast", "director"]
    difficulties = (["easy"] * 3 + ["medium"] * 5 + ["hard"] * 2) if mode != "daily" else ["easy", "easy", "medium", "medium", "medium", "hard", "hard"]
    result, used_questions, used_titles = [], set(), set()
    for index in range(count):
        requested_type, requested_difficulty = type_slots[index % len(type_slots)], difficulties[index % len(difficulties)]
        candidates = [requested_type] + [kind for kind in (personal_types if mode == "library" and index < 6 else general_types) if kind != requested_type]
        for question_type in candidates:
            target_pool = pool.indexes.get(question_type) or (library if question_type in {"in_library", "my_rating", "higher_rated"} else targets)
            target_pool = list(target_pool)
            rng.shuffle(target_pool)
            for target in target_pool:
                if _key(target) in used_titles and question_type not in {"my_rating", "higher_rated"}:
                    continue
                question = engine.generate(question_type, target, targets, rng, library)
                if not question or question.question_id in used_questions or (question_type == requested_type and question.difficulty != requested_difficulty):
                    continue
                result.append(question); used_questions.add(question.question_id); used_titles.add(_key(target)); break
            if len(result) > index:
                break
        if len(result) <= index:
            break
    return result


class QuizPoolService:
    """Shared bounded pools. Cache/in-flight state is process-local by design."""

    def __init__(self, db: Any, tmdb: Any, cache: Any) -> None:
        self.db, self.tmdb, self.cache = db, tmdb, cache
        self._inflight: dict[str, asyncio.Task] = {}
        self._inflight_lock = asyncio.Lock()

    async def _shared(self, key: str, loader):
        cache_started = perf_counter()
        cached = await self.cache.get(key)
        logger.info("quiz_cache_timing quiz_cache_access_ms=%.1f hit=%s", (perf_counter() - cache_started) * 1000, cached is not None)
        if cached is not None:
            return cached
        async with self._inflight_lock:
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(loader())
                self._inflight[key] = task
        try:
            return await task
        finally:
            if task.done():
                async with self._inflight_lock:
                    if self._inflight.get(key) is task:
                        self._inflight.pop(key, None)

    async def get_global_pool(self) -> QuizCandidatePool:
        return await self._shared("quiz_pool:global:v2", self._load_global_pool)

    async def _load_global_pool(self) -> QuizCandidatePool:
        started = perf_counter()
        rows = await self.db.get_quiz_catalog(limit=GLOBAL_POOL_LIMIT)
        catalog = [row for row in (rows or []) if isinstance(row, dict)]
        fallback_count = 0
        if len([row for row in catalog if _recognizable(row)]) < 12:
            for media_type in ("movie", "tv"):
                try:
                    data = await self.tmdb.discover_with_filters(media_type=media_type, sort_by="popularity.desc", page=1, vote_count_gte=100)
                    for item in (data or {}).get("results", []) if isinstance(data, dict) else []:
                        if isinstance(item, dict):
                            item["media_type"] = media_type
                            catalog.append(item)
                            fallback_count += 1
                except Exception:
                    logger.warning("quiz TMDB fallback failed", exc_info=True)
        index_started = perf_counter()
        pool = await asyncio.to_thread(build_candidate_pool, catalog[:GLOBAL_POOL_LIMIT])
        await self.cache.put("quiz_pool:global:v2", pool, ttl_sec=GLOBAL_POOL_TTL_SEC)
        logger.info("quiz_pool_timing quiz_pool_global_load_ms=%.1f quiz_pool_index_ms=%.1f quiz_tmdb_fallback_count=%d pool_size=%d", (index_started - started) * 1000, (perf_counter() - index_started) * 1000, fallback_count, len(pool.rows))
        return pool

    async def get_library_pool(self, user_id: int) -> QuizCandidatePool:
        key = f"quiz_pool:library:{user_id}:v2"
        return await self._shared(key, lambda: self._load_library_pool(user_id, key))

    @staticmethod
    def _rotate_sample(rows: list[dict[str, Any]], limit: int, rotation: int) -> list[dict[str, Any]]:
        unique = list({ _key(row): row for row in rows if isinstance(row, dict) and _key(row)[0] }.values())
        if len(unique) <= limit:
            return unique
        offset = (rotation * limit) % len(unique)
        window = unique[offset:] + unique[:offset]
        selected: list[dict[str, Any]] = []
        for media_type in ("movie", "tv"):
            selected.extend(row for row in window if _media_type(row) == media_type and row not in selected)
        selected.extend(row for row in window if _rating(row) is not None and row not in selected)
        selected.extend(row for row in window if (row.get("overview") or row.get("directors") or row.get("actors")) and row not in selected)
        selected.extend(row for row in window if row not in selected)
        return selected[:limit]

    async def _load_library_pool(self, user_id: int, key: str) -> QuizCandidatePool:
        started = perf_counter()
        count_method = getattr(self.db, "get_user_library_count", None)
        if count_method:
            library_count = max(0, int(await count_method(user_id) or 0))
        else:
            fallback_rows = await self.db.get_user_quiz_catalog(user_id)
            library_count = len(fallback_rows or [])
        if library_count < LIBRARY_MINIMUM:
            pool = await asyncio.to_thread(build_candidate_pool, [], [], library_count)
        else:
            rotation = int(perf_counter() // (15 * 60))
            sample_method = getattr(self.db, "get_user_quiz_catalog_sample", None)
            if sample_method:
                rows = await sample_method(user_id, limit=LIBRARY_SAMPLE_LIMIT, offset=(rotation * LIBRARY_SAMPLE_LIMIT) % max(1, library_count))
            else:
                rows = await self.db.get_user_quiz_catalog(user_id)
            sample = self._rotate_sample(rows or [], LIBRARY_SAMPLE_LIMIT, rotation)
            sample_done = perf_counter()
            global_pool = await self.get_global_pool()
            index_started = perf_counter()
            pool = await asyncio.to_thread(build_candidate_pool, global_pool.rows, sample, library_count)
            logger.info("quiz_pool_timing quiz_pool_library_load_ms=%.1f quiz_pool_index_ms=%.1f library_count=%d sample_size=%d", (sample_done - started) * 1000, (perf_counter() - index_started) * 1000, library_count, len(pool.library_rows))
        await self.cache.put(key, pool, ttl_sec=LIBRARY_POOL_TTL_SEC)
        return pool

    async def warm(self, mode: str, user_id: int | None = None) -> None:
        if mode == "library" and user_id is not None:
            await self.get_library_pool(user_id)
        else:
            await self.get_global_pool()
        await self.cache.put(f"quiz_prewarm:{mode}:v2", {"ready": True}, ttl_sec=GLOBAL_POOL_TTL_SEC)


_SESSION_LOCKS: dict[str, asyncio.Lock] = {}


class QuizService:
    def __init__(self, db: Any, tmdb: Any, session_cache: Any, daily_cache: Any | None = None, pool_service: QuizPoolService | None = None) -> None:
        self.db, self.tmdb, self.session_cache = db, tmdb, session_cache
        self.daily_cache = daily_cache or session_cache
        self.pool_service = pool_service or QuizPoolService(db, tmdb, session_cache)

    async def create_session(self, user_id: int, mode: str = "cinema", today: str | None = None) -> dict[str, Any] | None:
        started = perf_counter()
        if mode not in SESSION_SIZES:
            return None
        daily_date = today or date.today().isoformat()
        if mode == "library":
            library_pool = await self.pool_service.get_library_pool(user_id)
            if (library_pool.library_count or 0) < LIBRARY_MINIMUM:
                return {"locked": True, "mode": mode, "library_count": library_pool.library_count or 0, "required_library_count": LIBRARY_MINIMUM, "remaining": LIBRARY_MINIMUM - (library_pool.library_count or 0), "questions": []}
            pool = library_pool
        elif mode == "daily":
            if await self.daily_cache.get(f"quiz_daily_attempt_{user_id}_{daily_date}"):
                return {"locked": True, "mode": mode, "daily_date": daily_date, "daily_status": "completed", "questions": []}
            pool = None
        else:
            pool = await self.pool_service.get_global_pool()

        if mode == "daily":
            daily_key = f"quiz_daily_questions:{daily_date}:v2"
            private_questions = await self.daily_cache.get(daily_key)
            if not isinstance(private_questions, list) or len(private_questions) < SESSION_SIZES[mode]:
                pool = await self.pool_service.get_global_pool()
                seed = int.from_bytes(hashlib.sha256(f"daily:{daily_date}".encode()).digest()[:8], "big")
                composed = await asyncio.to_thread(compose_questions, pool, mode, None, SESSION_SIZES[mode], seed)
                private_questions = [question.private() for question in composed]
                if len(private_questions) >= SESSION_SIZES[mode]:
                    await self.daily_cache.put(daily_key, private_questions, ttl_sec=DAILY_QUESTIONS_TTL_SEC)
            questions = private_questions
        else:
            compose_started = perf_counter()
            composed = await asyncio.to_thread(
                compose_questions,
                pool,
                mode,
                pool.library_rows,
                SESSION_SIZES[mode],
                secrets.randbits(64),
            )
            questions = [question.private() for question in composed]
            logger.info("quiz_session_timing quiz_session_compose_ms=%.1f", (perf_counter() - compose_started) * 1000)
        if len(questions) < SESSION_SIZES[mode]:
            return None
        if mode == "daily":
            await self.daily_cache.put(f"quiz_daily_attempt_{user_id}_{daily_date}", {"reserved": True})
        stats = await self.db.get_user_stats(user_id) or {}
        if not isinstance(stats, dict):
            stats = {}
        session_id = secrets.token_urlsafe(16)
        state = {"mode": mode, "daily_date": daily_date if mode == "daily" else None, "questions": questions, "answers": [], "score": 0, "combo": 0, "best_combo": 0, "correct_count": 0, "stats": dict(stats), "stats_base": dict(stats), "xp_delta": 0, "quiz_total_delta": 0, "quiz_correct_delta": 0, "current_streak": int(stats.get("current_streak") or 0), "best_streak_candidate": int(stats.get("best_streak") or 0), "completion_persisted": False}
        await self.session_cache.put(f"quiz_session_{user_id}_{session_id}", state)
        logger.info("quiz_session_timing quiz_create_total_ms=%.1f mode=%s questions=%d", (perf_counter() - started) * 1000, mode, len(questions))
        return {"session_id": session_id, "mode": mode, "locked": False, "total": len(questions), "questions": [{**question, "index": index} for index, question in enumerate(questions)], "library_count": pool.library_count if mode == "library" else None, "daily_date": state["daily_date"]}

    @staticmethod
    def _score_answers(state: dict[str, Any], submitted_answers: list[dict[str, Any]]) -> dict[str, Any] | None:
        questions = state.get("questions") or []
        if not isinstance(questions, list) or not 0 < len(submitted_answers) <= len(questions):
            return None
        stats = dict(state.get("stats_base") or {})
        answers: list[dict[str, Any]] = []
        score = 0
        combo = 0
        best_combo = 0
        correct_count = 0
        xp_delta = 0
        last_message = ""
        for index, submitted in enumerate(submitted_answers):
            if not isinstance(submitted, dict):
                return None
            question = questions[index]
            question_id = submitted.get("question_id")
            selected = submitted.get("selected_answer")
            options = question.get("options") or []
            if (
                question_id != question.get("id")
                or not isinstance(selected, str)
                or selected not in options
            ):
                return None
            elapsed_ms = submitted.get("elapsed_ms")
            try:
                elapsed_ms = max(0, min(120_000, int(elapsed_ms or 0)))
            except (TypeError, ValueError):
                elapsed_ms = 0
            is_correct = selected == question.get("correct_answer")
            combo = combo + 1 if is_correct else 0
            speed_ratio = max(0.0, min(1.0, 1.0 - elapsed_ms / 15_000))
            score_earned = round(
                100
                * DIFFICULTY_MULTIPLIERS.get(question.get("difficulty"), 1.0)
                * min(1.5, 1 + max(0, combo - 1) * 0.1)
                * (1 + 0.25 * speed_ratio)
            ) if is_correct else 0
            score += score_earned
            best_combo = max(best_combo, combo)
            correct_count += int(is_correct)
            stats, last_message, question_xp = stats_service.process_quiz_answer(is_correct, stats)
            xp_delta += question_xp
            answers.append({"question_id": question_id, "selected_answer": selected, "elapsed_ms": elapsed_ms, "is_correct": is_correct})

        complete = len(answers) == len(questions)
        if complete:
            stats, completion_xp = stats_service.award_quiz_completion(stats)
            xp_delta += completion_xp
        result = {
            "correct": correct_count,
            "total": len(questions),
            "accuracy": round(correct_count / len(questions) * 100),
            "score": score,
            "best_combo": best_combo,
            "earned_xp": xp_delta,
        } if complete else None
        return {
            "answers": answers,
            "stats": stats,
            "message": last_message,
            "score": score,
            "combo": combo,
            "best_combo": best_combo,
            "correct_count": correct_count,
            "xp_delta": xp_delta,
            "complete": complete,
            "result": result,
        }

    async def complete_session(self, user_id: int, session_id: str, submitted_answers: list[dict[str, Any]]) -> dict[str, Any] | None:
        key = f"quiz_session_{user_id}_{session_id}"
        lock = _SESSION_LOCKS.setdefault(key, asyncio.Lock())
        async with lock:
            state = await self.session_cache.get(key)
            if not isinstance(state, dict):
                return None
            if state.get("completion_persisted") and isinstance(state.get("result"), dict):
                return {"complete": True, "result": state["result"], "stats": state.get("stats") or {}}
            scored = self._score_answers(state, submitted_answers)
            if not scored or not scored["complete"]:
                return None
            await self.db.update_user_stats(user_id, scored["stats"])
            state.update(scored)
            state["completion_persisted"] = True
            state["result"] = scored["result"]
            await self.session_cache.put(key, state)
            if state.get("mode") == "daily":
                await self.daily_cache.put(f"quiz_daily_result_{user_id}_{state.get('daily_date')}", scored["result"])
            return {"complete": True, "result": scored["result"], "stats": scored["stats"]}

    async def answer_session(self, user_id: int, session_id: str, question_id: str, answer: str, elapsed_ms: int | None = None) -> dict[str, Any] | None:
        started = perf_counter()
        key = f"quiz_session_{user_id}_{session_id}"
        lock = _SESSION_LOCKS.setdefault(key, asyncio.Lock())
        async with lock:
            state = await self.session_cache.get(key)
            if not isinstance(state, dict) or not isinstance(answer, str) or not answer.strip():
                return None
            questions, answers = state.get("questions") or [], state.get("answers") or []
            index = len(answers)
            if index >= len(questions) or questions[index].get("id") != question_id or answer not in (questions[index].get("options") or []):
                return None
            submitted = [*answers, {"question_id": question_id, "selected_answer": answer, "elapsed_ms": elapsed_ms}]
            scored = self._score_answers(state, submitted)
            if not scored:
                return None
            question = questions[index]
            is_correct = answer == question.get("correct_answer")
            previous_score = int(state.get("score") or 0)
            previous_xp = int(state.get("xp_delta") or 0)
            state.update(scored)
            response = {"is_correct": is_correct, "correct_answer": question.get("correct_answer") or "", "message": scored["message"], "stats": scored["stats"], "xp_earned": scored["xp_delta"] - previous_xp, "score_earned": scored["score"] - previous_score, "score": scored["score"], "combo": scored["combo"], "best_combo": scored["best_combo"], "question_index": index, "next_index": index + 1, "complete": scored["complete"]}
            if scored["complete"]:
                persist_started = perf_counter()
                await self.db.update_user_stats(user_id, scored["stats"])
                logger.info("quiz_answer_timing quiz_completion_persist_ms=%.1f", (perf_counter() - persist_started) * 1000)
                state["completion_persisted"] = True
                response["result"] = scored["result"]
                await self.session_cache.put(key, state)
                if state.get("mode") == "daily":
                    await self.daily_cache.put(f"quiz_daily_result_{user_id}_{state.get('daily_date')}", scored["result"])
                _SESSION_LOCKS.pop(key, None)
            else:
                await self.session_cache.put(key, state)
            logger.info("quiz_answer_timing quiz_answer_total_ms=%.1f complete=%s", (perf_counter() - started) * 1000, scored["complete"])
            return response


async def get_random_movie_id() -> int:
    from config import quiz_pool_service
    pool = await quiz_pool_service.get_global_pool()
    return _key(random.choice(pool.rows))[0] if pool.rows else 0


async def build_quiz(movie_id: int, media_type: str = "movie") -> dict[str, Any] | None:
    from config import quiz_pool_service
    pool = await quiz_pool_service.get_global_pool()
    target = next((row for row in pool.rows if _key(row) == (movie_id, media_type)), None)
    if not target:
        return None
    engine = QuestionEngine(pool); question = engine.description_title(target, pool.rows, random.Random()) or engine.poster_title(target, pool.rows, random.Random())
    return {"question": question.prompt, "correct": question.correct_answer, "options": list(question.options), "question_id": question.question_id} if question else None
