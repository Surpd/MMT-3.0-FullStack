import os
import unittest
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

os.environ.setdefault("BOT_TOKEN", "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
os.environ.setdefault("TMDB_API_KEY", "test-tmdb-key")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-supabase-key")

from services.quiz_service import build_candidate_pool
from web_app.api import handle_get_library, handle_get_quiz, handle_get_quiz_meta, handle_get_stats
from web_app.auth import auth_middleware


TEST_USER_ID = 900000001


class FakeCache:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def put(self, key, value, ttl_sec=None):
        self.values[key] = value

    async def delete(self, key):
        self.values.pop(key, None)


class SmokeDb:
    def __init__(self):
        self.stats = {"points": 12, "quiz_total": 3, "quiz_correct": 2, "current_streak": 1, "best_streak": 2}
        self.movies = [
            {
                "id": 900001000 + index,
                "movie_id": 900001000 + index,
                "title": f"Smoke Movie {index + 1:02d}",
                "media_type": "movie",
                "year": 2000 + index,
                "overview": f"A sufficiently long deterministic smoke-test description for movie {index + 1:02d}.",
                "poster_url": "/smoke.jpg",
                "actors": [f"Smoke Actor {index + 1:02d}"],
                "directors": [f"Smoke Director {index + 1:02d}"],
                "tmdb_vote_count": 100,
            }
            for index in range(25)
        ]
        self.catalog = self.movies + [
            {
                **movie,
                "id": 900001100 + index,
                "movie_id": 900001100 + index,
                "title": f"Smoke Catalog Movie {index + 1:02d}",
            }
            for index, movie in enumerate(self.movies[:15])
        ]

    async def get_user_stats(self, user_id):
        return self.stats

    async def get_user_library_count(self, user_id):
        return len(self.movies)

    async def get_webapp_library(self, user_id, status, offset, limit):
        return [
            {"movie_id": movie["id"], "media_type": "movie", "rating": index % 5 + 1, "movies": movie}
            for index, movie in enumerate(self.movies[offset:offset + limit])
        ], len(self.movies)

    async def get_user_quiz_catalog_sample(self, user_id, limit=100, offset=0):
        return self.movies[offset:offset + limit]

    async def get_quiz_catalog(self, limit=500):
        return self.catalog[:limit]


class SmokePoolService:
    def __init__(self, db, cache):
        self.db = db
        self.cache = cache

    async def get_global_pool(self):
        return build_candidate_pool(self.db.catalog)

    async def get_library_pool(self, user_id):
        return build_candidate_pool(self.db.catalog, self.db.movies, len(self.db.movies))


class AuthenticatedSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticated_feature_endpoints_work_with_test_header(self):
        db = SmokeDb()
        session_cache = FakeCache()
        daily_cache = FakeCache()
        pool_service = SmokePoolService(db, session_cache)

        app = web.Application(middlewares=[auth_middleware])
        app.router.add_get("/api/stats", handle_get_stats)
        app.router.add_get("/api/library", handle_get_library)
        app.router.add_get("/api/quiz/meta", handle_get_quiz_meta)
        app.router.add_get("/api/quiz", handle_get_quiz)
        client = TestClient(TestServer(app))

        with patch.dict(os.environ, {"TEST_MODE": "true", "RUNTIME_ENV": "development"}, clear=False), patch(
            "web_app.api.db", db
        ), patch("web_app.api.session_cache", session_cache), patch(
            "web_app.api.daily_cache", daily_cache
        ), patch("web_app.api.quiz_pool_service", pool_service):
            await client.start_server()
            try:
                headers = {"X-Test-User-Id": str(TEST_USER_ID)}
                stats = await client.get(f"/api/stats?user_id={TEST_USER_ID}", headers=headers)
                library = await client.get("/api/library?user_id=900000001&status=liked&page=1", headers=headers)
                meta = await client.get("/api/quiz/meta", headers=headers)
                quiz = await client.get("/api/quiz?mode=library", headers=headers)

                self.assertEqual(stats.status, 200)
                self.assertEqual((await stats.json())["stats"]["points"], 12)
                self.assertEqual(library.status, 200)
                self.assertEqual((await library.json())["total"], 25)
                self.assertTrue((await meta.json())["library_unlocked"])
                self.assertEqual((await meta.json())["library_count"], 25)
                self.assertEqual(quiz.status, 200, await quiz.text())
                self.assertEqual(len((await quiz.json())["quiz"]["questions"]), 10)
            finally:
                await client.close()


if __name__ == "__main__":
    unittest.main()
