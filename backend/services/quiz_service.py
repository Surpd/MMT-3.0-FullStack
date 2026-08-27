from __future__ import annotations

import hashlib
import random
import secrets
from dataclasses import dataclass
from datetime import date
from typing import Any

from services.stats_service import stats_service

LIBRARY_MINIMUM = 20
SESSION_SIZES = {"cinema": 10, "library": 10, "daily": 7}
DIFFICULTY_MULTIPLIERS = {"easy": 1.0, "medium": 1.25, "hard": 1.5}


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
    value = row.get("poster_url") or row.get("poster_path") or ""
    if not isinstance(value, str):
        return ""
    return value if value.startswith("http") else f"https://image.tmdb.org/t/p/w500{value}" if value else ""


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


class QuestionEngine:
    """Small, testable generators over one already-loaded catalog."""

    def _distractors(self, target: dict[str, Any], catalog: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
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
        if not _poster(target) or not correct:
            return None
        return self._make("poster_title", "easy", "Как называется это произведение?", correct, [correct, *[_title(row) for row in self._distractors(target, catalog, rng)]][:4], target, rng)

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
        person = next((name for name in people if sum(name in _list_value(row.get("actors") or row.get("directors")) for row in catalog) == 1), None)
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


def compose_questions(catalog: list[dict[str, Any]], mode: str = "cinema", library: list[dict[str, Any]] | None = None, count: int | None = None, seed: int | None = None) -> list[QuizQuestion]:
    engine, rng = QuestionEngine(), random.Random(seed)
    count = count or SESSION_SIZES.get(mode, 10)
    personal_types = ["in_library", "not_in_library", "my_rating", "higher_rated"]
    general_types = ["poster_title", "description_title", "director", "cast", "filmography", "release_year", "chronology"]
    targets, library = [row for row in catalog if _recognizable(row)], library or []
    if mode == "library":
        type_slots = [personal_types[i % len(personal_types)] for i in range(min(6, count))] + [general_types[i % len(general_types)] for i in range(max(0, count - 6))]
    elif mode == "daily":
        type_slots = ["poster_title", "release_year", "description_title", "director", "cast", "chronology", "filmography"]
    else:
        type_slots = ["poster_title", "release_year", "description_title", "director", "cast", "description_title", "filmography", "release_year", "chronology", "cast"]
    difficulties = (["easy"] * 3 + ["medium"] * 5 + ["hard"] * 2) if mode != "daily" else ["easy", "easy", "medium", "medium", "medium", "hard", "hard"]
    result, used_questions, used_titles = [], set(), set()
    for index in range(count):
        requested_type, requested_difficulty = type_slots[index % len(type_slots)], difficulties[index % len(difficulties)]
        candidates = [requested_type] + [kind for kind in (personal_types if mode == "library" and index < 6 else general_types) if kind != requested_type]
        rng.shuffle(targets)
        for question_type in candidates:
            target_pool = library if question_type in {"in_library", "my_rating", "higher_rated"} else targets
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


class QuizService:
    def __init__(self, db: Any, tmdb: Any, session_cache: Any, daily_cache: Any | None = None) -> None:
        self.db, self.tmdb, self.session_cache = db, tmdb, session_cache
        self.daily_cache = daily_cache or session_cache

    async def _global_catalog(self) -> list[dict[str, Any]]:
        rows = await self.db.get_quiz_catalog(limit=500)
        catalog = [row for row in (rows or []) if isinstance(row, dict)]
        if len(catalog) >= 12:
            return catalog
        for media_type in ("movie", "tv"):
            try:
                data = await self.tmdb.discover_with_filters(media_type=media_type, sort_by="popularity.desc", page=1, vote_count_gte=100)
                for item in (data or {}).get("results", []) if isinstance(data, dict) else []:
                    if isinstance(item, dict):
                        item["media_type"] = media_type; catalog.append(item)
            except Exception:
                continue
        unique = {}
        for row in catalog:
            if _key(row)[0]:
                unique[_key(row)] = row
        return list(unique.values())

    async def _library_catalog(self, user_id: int) -> list[dict[str, Any]]:
        rows = await self.db.get_user_quiz_catalog(user_id)
        return [row for row in (rows or []) if isinstance(row, dict)]

    async def create_session(self, user_id: int, mode: str = "cinema", today: str | None = None) -> dict[str, Any] | None:
        if mode not in SESSION_SIZES:
            return None
        library = await self._library_catalog(user_id) if mode == "library" else []
        if mode == "library" and len(library) < LIBRARY_MINIMUM:
            return {"locked": True, "mode": mode, "library_count": len(library), "required_library_count": LIBRARY_MINIMUM, "remaining": LIBRARY_MINIMUM - len(library), "questions": []}
        daily_date = today or date.today().isoformat()
        if mode == "daily" and await self.daily_cache.get(f"quiz_daily_attempt_{user_id}_{daily_date}"):
            return {"locked": True, "mode": mode, "daily_date": daily_date, "daily_status": "completed", "questions": []}
        if mode == "daily":
            await self.daily_cache.put(f"quiz_daily_attempt_{user_id}_{daily_date}", {"reserved": True})
        catalog = await self._global_catalog()
        if mode == "daily":
            catalog = sorted(catalog, key=_key)
        seed = int.from_bytes(hashlib.sha256(f"daily:{daily_date}".encode()).digest()[:8], "big") if mode == "daily" else secrets.randbits(64)
        questions = compose_questions(catalog, mode=mode, library=library, count=SESSION_SIZES[mode], seed=seed)
        if len(questions) < SESSION_SIZES[mode]:
            if mode == "daily":
                await self.daily_cache.delete(f"quiz_daily_attempt_{user_id}_{daily_date}")
            return None
        session_id = secrets.token_urlsafe(16)
        state = {"mode": mode, "daily_date": daily_date if mode == "daily" else None, "questions": [question.private() for question in questions], "answers": [], "score": 0, "combo": 0, "best_combo": 0, "correct_count": 0}
        await self.session_cache.put(f"quiz_session_{user_id}_{session_id}", state)
        return {"session_id": session_id, "mode": mode, "locked": False, "total": len(questions), "questions": [question.public(index) for index, question in enumerate(questions)], "library_count": len(library) if mode == "library" else None, "daily_date": state["daily_date"]}

    async def answer_session(self, user_id: int, session_id: str, question_id: str, answer: str, elapsed_ms: int | None = None) -> dict[str, Any] | None:
        key, state = f"quiz_session_{user_id}_{session_id}", await self.session_cache.get(f"quiz_session_{user_id}_{session_id}")
        if not isinstance(state, dict) or not isinstance(answer, str) or not answer.strip():
            return None
        questions, answers = state.get("questions") or [], state.get("answers") or []
        index = len(answers)
        if index >= len(questions) or questions[index].get("id") != question_id or answer not in (questions[index].get("options") or []):
            return None
        question, is_correct = questions[index], answer == questions[index].get("correct_answer")
        combo = int(state.get("combo") or 0) + 1 if is_correct else 0
        try:
            speed_ratio = max(0.0, min(1.0, 1.0 - int(elapsed_ms or 0) / 15000)) if elapsed_ms is not None else 0.0
        except (TypeError, ValueError):
            speed_ratio = 0.0
        score = round(100 * DIFFICULTY_MULTIPLIERS.get(question.get("difficulty"), 1.0) * min(1.5, 1 + max(0, combo - 1) * 0.1) * (1 + 0.25 * speed_ratio)) if is_correct else 0
        state["answers"] = [*answers, {"question_id": question_id, "is_correct": is_correct}]
        state["score"] = int(state.get("score") or 0) + score; state["combo"] = combo; state["best_combo"] = max(int(state.get("best_combo") or 0), combo); state["correct_count"] = int(state.get("correct_count") or 0) + int(is_correct)
        complete = len(state["answers"]) == len(questions)
        current_stats = await self.db.get_user_stats(user_id) or {}
        new_stats, message, xp_earned = stats_service.process_quiz_answer(is_correct, current_stats)
        if complete:
            new_stats, completion_xp = stats_service.award_quiz_completion(new_stats); xp_earned += completion_xp
        await self.db.update_user_stats(user_id, new_stats)
        response = {"is_correct": is_correct, "correct_answer": question.get("correct_answer") or "", "message": message, "stats": new_stats, "xp_earned": xp_earned, "score_earned": score, "score": state["score"], "combo": combo, "best_combo": state["best_combo"], "question_index": index, "next_index": index + 1, "complete": complete}
        if complete:
            result = {"correct": state["correct_count"], "total": len(questions), "accuracy": round(state["correct_count"] / len(questions) * 100), "score": state["score"], "best_combo": state["best_combo"], "earned_xp": int(sum(item.get("is_correct", False) for item in state["answers"]) * 10) + 10}
            response["result"] = result; await self.session_cache.delete(key)
            if state.get("mode") == "daily":
                await self.daily_cache.put(f"quiz_daily_result_{user_id}_{state.get('daily_date')}", result)
        else:
            await self.session_cache.put(key, state)
        return response


async def get_random_movie_id() -> int:
    from config import db, tmdb, session_cache
    rows = [row for row in await QuizService(db, tmdb, session_cache)._global_catalog() if _recognizable(row)]
    return _key(random.choice(rows))[0] if rows else 0


async def build_quiz(movie_id: int, media_type: str = "movie") -> dict[str, Any] | None:
    from config import db, tmdb, session_cache
    service = QuizService(db, tmdb, session_cache); catalog = await service._global_catalog(); target = next((row for row in catalog if _key(row) == (movie_id, media_type)), None)
    if not target:
        return None
    engine = QuestionEngine(); question = engine.description_title(target, catalog, random.Random()) or engine.poster_title(target, catalog, random.Random())
    return {"question": question.prompt, "correct": question.correct_answer, "options": list(question.options), "question_id": question.question_id} if question else None
