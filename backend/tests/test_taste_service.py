import asyncio
import unittest
from unittest.mock import patch

from services.taste_service import normalize_title_genres, normalize_tmdb_genre, get_taste_summary


class TasteServiceTests(unittest.TestCase):
    def test_composite_genres_are_split_with_fractional_weights(self):
        self.assertEqual(normalize_tmdb_genre("Action & Adventure"), {"Action": 0.5, "Adventure": 0.5})
        self.assertEqual(normalize_tmdb_genre("Sci-Fi & Fantasy"), {"Science Fiction": 0.5, "Fantasy": 0.5})
        self.assertEqual(normalize_tmdb_genre("War & Politics"), {"War": 0.5})

    def test_title_genres_are_normalized_to_one(self):
        result = normalize_title_genres(["Drama", "Action & Adventure"])
        self.assertEqual(result, {"Drama": 0.5, "Action": 0.25, "Adventure": 0.25})

    def test_summary_uses_liked_rows_and_country_coverage(self):
        class Query:
            def select(self, *_args): return self
            def eq(self, *_args): return self

        class FakeDb:
            _client = type("Client", (), {"table": lambda *_args: Query()})()
            async def _execute(self, _query):
                return type("Response", (), {"data": [
                    {"rating": 5, "media_type": "movie", "movies": {
                        "media_type": "movie", "genres_array": ["Action", "Comedy"],
                        "directors": ["Director A"], "actors": ["Actor A"], "year": "2001",
                        "production_countries": [{"iso_3166_1": "US"}, {"iso_3166_1": "GB"}],
                    }},
                    {"rating": 4, "media_type": "tv", "movies": {
                        "media_type": "tv", "genres_array": ["Drama", "Action & Adventure"],
                        "directors": ["Director A"], "actors": ["Actor B"], "year": "2010",
                        "origin_country": ["GB"],
                    }},
                    {"rating": None, "media_type": "movie", "movies": {
                        "media_type": "movie", "genres_array": ["Drama"],
                        "directors": ["Director A"], "year": "2003",
                        "production_countries": [{"iso_3166_1": "US"}],
                    }},
                ]})()

        with patch("services.taste_service.db", FakeDb()):
            summary = asyncio.run(get_taste_summary(7))

        self.assertAlmostEqual(sum(item["share"] for item in summary["genres"]), 100.0)
        self.assertEqual(summary["movie_vs_series"]["total"], 3)
        self.assertEqual(summary["directors"][0]["name"], "Director A")
        self.assertEqual(summary["directors"][0]["rating"], 4.5)
        self.assertEqual({item["name"] for item in summary["countries"]}, {"США", "Великобритания"})
        self.assertAlmostEqual(sum(item["share"] for item in summary["countries"]), 100.0)
        self.assertEqual(summary["country_coverage"]["coverage_percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
