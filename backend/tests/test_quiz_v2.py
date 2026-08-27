import asyncio
import unittest

from services.cache import MemoryCache
from services.quiz_service import LIBRARY_MINIMUM, QuizQuestion, QuizService, QuestionEngine, compose_questions
from services.stats_service import StatsService


def catalog(size=24):
    rows = []
    for index in range(size):
        media_type = "tv" if index % 5 == 0 else "movie"
        rows.append({
            "id": index + 1,
            "media_type": media_type,
            "title": f"Title {index + 1}",
            "year": str(2000 + index),
            "overview": f"A sufficiently long description for title {index + 1} with a clear story and useful details.",
            "poster_url": f"https://image.tmdb.org/t/p/w500/{index + 1}.jpg",
            "directors": [f"Director {index}"],
            "actors": [f"Actor {index}", f"Actor {index}b"],
            "tmdb_vote_count": 1000 - index,
        })
    return rows


class FakeDb:
    def __init__(self, rows, library=None):
        self.rows = rows
        self.library = library or []
        self.stats = {"points": 20, "quiz_total": 0, "quiz_correct": 0, "current_streak": 0, "best_streak": 0}

    async def get_quiz_catalog(self, limit=500):
        return self.rows[:limit]

    async def get_user_quiz_catalog(self, user_id):
        return self.library

    async def get_user_stats(self, user_id):
        return dict(self.stats)

    async def update_user_stats(self, user_id, stats):
        self.stats = dict(stats)


class FakeTmdb:
    async def discover_with_filters(self, **kwargs):
        return {"results": []}


class QuizV2Tests(unittest.TestCase):
    def test_cinema_session_has_unique_questions_and_one_correct_option(self):
        questions = compose_questions(catalog(), seed=4)
        self.assertEqual(len(questions), 10)
        self.assertEqual(len({question.question_id for question in questions}), 10)
        for question in questions:
            self.assertIn(question.correct_answer, question.options)
            self.assertEqual(sum(option == question.correct_answer for option in question.options), 1)

    def test_library_gate_and_unlocked_session(self):
        rows = catalog()
        locked = QuizService(FakeDb(rows, rows[:12]), FakeTmdb(), MemoryCache(3600))
        locked_result = asyncio.run(locked.create_session(1, "library"))
        self.assertTrue(locked_result["locked"])
        self.assertEqual(locked_result["remaining"], LIBRARY_MINIMUM - 12)

        unlocked = QuizService(FakeDb(rows, rows[:20]), FakeTmdb(), MemoryCache(3600))
        unlocked_result = asyncio.run(unlocked.create_session(1, "library"))
        self.assertFalse(unlocked_result["locked"])
        self.assertEqual(len(unlocked_result["questions"]), 10)

    def test_rating_generator_skips_missing_rating_data(self):
        row = catalog(4)[0]
        self.assertIsNone(QuestionEngine().my_rating(row, catalog(4), catalog(4), __import__("random").Random(1)))

    def test_wrong_answer_does_not_reduce_xp_and_resets_combo(self):
        service = StatsService()
        stats, _, xp = service.process_quiz_answer(False, {"points": 100, "current_streak": 3, "best_streak": 3, "quiz_total": 2, "quiz_correct": 2})
        self.assertEqual(stats["points"], 100)
        self.assertEqual(stats["current_streak"], 0)
        self.assertEqual(xp, 0)

    def test_daily_is_deterministic_for_date_and_changes_for_other_date(self):
        rows = catalog()
        first = QuizService(FakeDb(rows), FakeTmdb(), MemoryCache(3600))
        second = QuizService(FakeDb(rows), FakeTmdb(), MemoryCache(3600))
        day_one = asyncio.run(first.create_session(1, "daily", today="2026-08-27"))
        same_day = asyncio.run(second.create_session(2, "daily", today="2026-08-27"))
        next_day = asyncio.run(second.create_session(3, "daily", today="2026-08-28"))
        self.assertEqual(day_one["questions"], same_day["questions"])
        self.assertNotEqual(day_one["questions"], next_day["questions"])

    def test_daily_attempt_is_reserved_for_the_day(self):
        cache = MemoryCache(3600)
        service = QuizService(FakeDb(catalog()), FakeTmdb(), cache)
        first = asyncio.run(service.create_session(1, "daily", today="2026-08-27"))
        second = asyncio.run(service.create_session(1, "daily", today="2026-08-27"))
        self.assertFalse(first["locked"])
        self.assertTrue(second["locked"])

    def test_answer_is_server_side_and_wrong_option_is_rejected(self):
        db = FakeDb(catalog())
        cache = MemoryCache(3600)
        service = QuizService(db, FakeTmdb(), cache)
        session = asyncio.run(service.create_session(1, "cinema"))
        question = session["questions"][0]
        bad = asyncio.run(service.answer_session(1, session["session_id"], question["id"], "not-an-option"))
        self.assertIsNone(bad)
        result = asyncio.run(service.answer_session(1, session["session_id"], question["id"], question["options"][0]))
        self.assertIsInstance(result["is_correct"], bool)
        private = asyncio.run(cache.get(f"quiz_session_1_{session['session_id']}"))
        selected_is_correct = question["options"][0] == private["questions"][0]["correct_answer"]
        self.assertEqual(result["score"] == 0, not selected_is_correct)
        self.assertEqual(db.stats["points"], 20 + (10 if result["is_correct"] else 0))

    def test_media_type_is_preserved(self):
        questions = compose_questions(catalog(), mode="daily", seed=2)
        self.assertIn("tv", {question.media_type for question in questions})


if __name__ == "__main__":
    unittest.main()
