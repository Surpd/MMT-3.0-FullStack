import asyncio
import unittest
from unittest.mock import patch

import services.search_service as search_service
from services.tmdb import MovieSearchResult


class SearchHardeningTests(unittest.TestCase):
    def test_ai_payload_is_bounded_validated_and_deduplicated(self):
        content = '{"movies":[{"title":"A","year":2020,"media_type":"movie"},{"title":"A","year":2020,"media_type":"movie"},{"title":"bad","year":"not-year","media_type":"movie"},{"title":"B","year":2021,"media_type":"tv"}]} trailing'
        self.assertEqual(search_service._parse_ai_movies(content), [
            {"title": "A", "year": 2020, "media_type": "movie"},
            {"title": "B", "year": 2021, "media_type": "tv"},
        ])

    def test_ai_match_rejects_year_mismatch(self):
        items = [
            MovieSearchResult(movie_id=1, title="Right", year="2020", media_type="tv"),
            MovieSearchResult(movie_id=2, title="Right", year="2020", media_type="movie"),
        ]
        self.assertEqual(search_service._pick_ai_match(items, {"title": "Right", "year": 2020, "media_type": "movie"}).movie_id, 2)
        self.assertIsNone(search_service._pick_ai_match(items, {"title": "Right", "year": 2021, "media_type": "movie"}))

    def test_deprecated_model_response_is_logged_and_returns_empty(self):
        class FakeResponse:
            status = 404

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            async def json(self, **_):
                return {"error": {"code": "model_not_found"}}

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            def post(self, *_args, **_kwargs):
                return FakeResponse()

        with patch.object(search_service, "GROQ_API_KEY", "test-key"):
            with patch.object(search_service.aiohttp, "ClientSession", return_value=FakeSession()):
                with self.assertLogs(level="ERROR") as logs:
                    result = asyncio.run(
                        search_service.get_ai_movie_recommendations("уютный фильм про путешествие")
                    )

        self.assertEqual(result, [])
        self.assertIn("AI upstream error status=404 code=model_not_found", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
