import os
import unittest
from unittest.mock import patch

os.environ.setdefault("BOT_TOKEN", "test-bot-token")
os.environ.setdefault("TMDB_API_KEY", "test-tmdb-key")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-supabase-key")

from web_app.api import _parse_bounded_int, _parse_media_type, _parse_rating, handle_quiz_answer


class FakeApiRequest(dict):
    async def json(self):
        return self["payload"]


class FakeQuizCache:
    def __init__(self):
        self.values = {"quiz_123_token": {"correct": "A", "options": ["A", "B"]}}

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, key):
        self.values.pop(key, None)


class FakeStatsDb:
    async def get_user_stats(self, user_id):
        return {"points": 0, "quiz_total": 0, "quiz_correct": 0, "current_streak": 0, "best_streak": 0}

    async def update_user_stats(self, user_id, stats):
        self.updated = stats


class ApiValidationTests(unittest.TestCase):
    def test_rating_accepts_only_integer_range(self):
        self.assertEqual(_parse_rating(1), 1)
        self.assertEqual(_parse_rating(5), 5)
        for value in (0, -1, 6, 1.0, True, False, "1.0", "bad", None):
            self.assertIsNone(_parse_rating(value), value)

    def test_bounded_integer_rejects_unbounded_or_malformed_values(self):
        self.assertEqual(_parse_bounded_int("0", "cursor", 0, 10_000), 0)
        self.assertEqual(_parse_bounded_int("10000", "cursor", 0, 10_000), 10_000)
        for value in ("", "-1", "10001", "1.0", True, None):
            self.assertIsNone(_parse_bounded_int(value, "cursor", 0, 10_000), value)

    def test_media_type_is_allowlisted(self):
        self.assertEqual(_parse_media_type("movie"), "movie")
        self.assertEqual(_parse_media_type("tv"), "tv")
        self.assertIsNone(_parse_media_type("person"))

    def test_quiz_uses_server_answer_and_consumes_token(self):
        request = FakeApiRequest(
            authenticated_user_id=123,
            local_dev=False,
            payload={"user_id": 123, "quiz_id": "token", "answer": "A", "correct": False},
        )
        cache = FakeQuizCache()
        with patch("web_app.api.session_cache", cache), patch("web_app.api.db", FakeStatsDb()):
            response = __import__("asyncio").run(handle_quiz_answer(request))
        self.assertEqual(response.status, 200)
        self.assertNotIn("quiz_123_token", cache.values)

    def test_quiz_token_cannot_be_replayed(self):
        request = FakeApiRequest(
            authenticated_user_id=123,
            local_dev=False,
            payload={"user_id": 123, "quiz_id": "token", "answer": "A"},
        )
        cache = FakeQuizCache()
        with patch("web_app.api.session_cache", cache), patch("web_app.api.db", FakeStatsDb()):
            __import__("asyncio").run(handle_quiz_answer(request))
            response = __import__("asyncio").run(handle_quiz_answer(request))
        self.assertEqual(response.status, 400)


if __name__ == "__main__":
    unittest.main()
