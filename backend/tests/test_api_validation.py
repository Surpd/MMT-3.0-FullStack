import os
import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("BOT_TOKEN", "test-bot-token")
os.environ.setdefault("TMDB_API_KEY", "test-tmdb-key")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-supabase-key")

from web_app.api import _merge_recommendation_tv_metadata, _parse_bounded_int, _parse_media_type, _parse_rating, _parse_recommendation_filters, handle_quiz_answer, handle_swipe


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

    def test_recommendation_year_range_is_validated(self):
        request = type("Request", (), {"query": {"min_year": "2000", "max_year": "2010"}})()
        self.assertEqual(_parse_recommendation_filters(request)[1:3], (2000, 2010))
        invalid = type("Request", (), {"query": {"min_year": "2010", "max_year": "2000"}})()
        with self.assertRaises(Exception):
            _parse_recommendation_filters(invalid)

    def test_swipe_retry_with_same_action_id_updates_taste_once(self):
        class SwipeDb:
            def __init__(self):
                self.action_id = None
                self.upserts = 0

            async def get_movie(self, _movie_id, _media_type):
                return {"id": 10, "media_type": "movie"}

            async def get_user_movie(self, _user_id, _movie_id, _media_type):
                return SimpleNamespace(action_id=self.action_id) if self.action_id else None

            async def upsert_user_movie(self, **kwargs):
                self.action_id = kwargs.get("action_id")
                self.upserts += 1

        class SwipeRecommendations:
            def __init__(self):
                self.updates = 0

            async def update_taste_profile(self, *_args):
                self.updates += 1

        swipe_db = SwipeDb()
        recommendations = SwipeRecommendations()
        request = FakeApiRequest(
            authenticated_user_id=123,
            local_dev=False,
            payload={"user_id": 123, "movie_id": 10, "action": "liked", "media_type": "movie", "action_id": "retry-1"},
        )
        with patch("web_app.api.db", swipe_db), patch("web_app.api.recommendation_service", recommendations):
            first = asyncio.run(handle_swipe(request))
            second = asyncio.run(handle_swipe(request))
        self.assertEqual(first.status, 200)
        self.assertEqual(second.status, 200)
        self.assertEqual(swipe_db.upserts, 1)
        self.assertEqual(recommendations.updates, 1)

    def test_recommendation_tv_metadata_fills_incomplete_db_row(self):
        row = {"media_type": "tv", "seasons": 0, "tv_status": ""}
        recommendation = {"seasons": 3, "tv_status": "Ended"}
        self.assertEqual(_merge_recommendation_tv_metadata(row, recommendation)["seasons"], 3)
        self.assertEqual(_merge_recommendation_tv_metadata(row, recommendation)["tv_status"], "Ended")

    def test_recommendation_metadata_does_not_change_movies_or_valid_tv_data(self):
        movie = {"media_type": "movie", "seasons": 0}
        self.assertEqual(_merge_recommendation_tv_metadata(movie, {"seasons": 4}), movie)
        tv = {"media_type": "tv", "seasons": 2, "tv_status": "Returning Series"}
        self.assertEqual(_merge_recommendation_tv_metadata(tv, {"seasons": 4, "tv_status": "Ended"}), tv)

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
