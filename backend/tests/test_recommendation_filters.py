import asyncio
import unittest
from unittest.mock import AsyncMock

from services.recommendation_service import RecommendationService


class RecommendationFilterTests(unittest.TestCase):
    def setUp(self):
        self.tmdb = type("Tmdb", (), {"discover_with_filters": AsyncMock(return_value={"results": []})})()
        self.service = RecommendationService(object(), self.tmdb, object(), object())

    def test_novice_path_forwards_year_and_rating_filters(self):
        asyncio.run(self.service._fetch_novice_hits(set(), "movie", [], 2010, 8.5))

        kwargs = self.tmdb.discover_with_filters.await_args.kwargs
        self.assertEqual(kwargs["year_from"], 2010)
        self.assertEqual(kwargs["vote_average.gte"], 8.5)

    def test_lifeboat_keeps_explicit_filters(self):
        asyncio.run(self.service._discover_with_cascade([], set(), "movie", 2015, 7.5))

        kwargs = self.tmdb.discover_with_filters.await_args.kwargs
        self.assertEqual(kwargs["year_from"], 2015)
        self.assertEqual(kwargs["vote_average.gte"], 7.5)


if __name__ == "__main__":
    unittest.main()
