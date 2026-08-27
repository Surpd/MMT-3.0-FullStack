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
            async def get_taste_profile(self, _user_id):
                return {
                    "interaction_count": 3,
                    "genres_jsonb": {"Action": 0.4, "Comedy": 0.3, "Drama": 0.3},
                    "directors_jsonb": {"Director A": 1.0},
                    "countries_jsonb": {"US": 0.5, "GB": 0.5},
                    "eras_jsonb": {"2000s": 1.0},
                    "keywords_jsonb": {"heist": 1.0},
                    "profile_version": 2,
                }

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
        self.assertEqual({item["name"] for item in summary["countries"]}, {"США", "Великобритания"})
        self.assertAlmostEqual(sum(item["share"] for item in summary["countries"]), 100.0)
        self.assertEqual(summary["country_coverage"]["coverage_percent"], 100.0)

    def test_summary_uses_snapshot_and_exposes_maturity(self):
        class FakeDb:
            async def get_taste_profile(self, _user_id):
                return {"interaction_count": 1, "genres_jsonb": {"Mystery": 1.0}}

            async def _execute(self, _query):
                return type("Response", (), {"data": []})()

        with patch("services.taste_service.db", FakeDb()):
            summary = asyncio.run(get_taste_summary(7))
        self.assertEqual(summary["taste_source"], "user_taste_profiles")
        self.assertEqual(summary["maturity"], "early")
        self.assertEqual(summary["genres"][0]["name"], "Детектив")

    def test_empty_snapshot_does_not_rebuild_a_second_profile(self):
        class FakeDb:
            async def get_taste_profile(self, _user_id):
                return None

        with patch("services.taste_service.db", FakeDb()):
            summary = asyncio.run(get_taste_summary(7))
        self.assertEqual(summary["maturity"], "empty")
        self.assertEqual(summary["genres"], [])


if __name__ == "__main__":
    unittest.main()
