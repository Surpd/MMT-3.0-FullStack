import unittest

from services.recommendation_service import RecommendationService
from scripts.bootstrap_taste_profiles import group_rows, missing_metadata


class TasteBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.service = RecommendationService(None, None, None, None)

    def test_aggregation_is_order_independent_and_archive_is_ignored(self):
        rows = [
            {"status": "liked", "rating": 5, "media_type": "movie", "movies": {"genres_array": ["Криминал"]}},
            {"status": "watchlist", "media_type": "tv", "movies": {"genres_array": ["Анимация"]}},
            {"status": "archive", "media_type": "movie", "movies": {"genres_array": ["Ужасы"]}},
        ]
        first = self.service._bootstrap_profile_from_rows(rows)
        second = self.service._bootstrap_profile_from_rows(list(reversed(rows)))
        self.assertEqual(first, second)
        self.assertNotIn("Horror", first["genres"])
        self.assertGreater(first["genres"]["Crime"], first["genres"]["Animation"])
        self.assertEqual(first["interaction_count"], 2)
        self.assertEqual(first["movie_modifiers"]["genres"], {"Crime": 1.0})
        self.assertEqual(first["tv_modifiers"]["genres"], {"Animation": 1.0})

    def test_rating_and_missing_metadata_are_safe(self):
        high = self.service._bootstrap_profile_from_rows([
            {"status": "liked", "rating": 5, "movies": {"genres_array": ["Криминал"]}},
            {"status": "liked", "rating": 5, "movies": {"genres_array": ["Анимация"]}},
        ])
        low = self.service._bootstrap_profile_from_rows([
            {"status": "liked", "rating": 2, "movies": {"genres_array": ["Криминал"]}},
            {"status": "liked", "rating": 5, "movies": {"genres_array": ["Анимация"]}},
        ])
        self.assertGreater(high["genres"]["Crime"], low["genres"]["Crime"])
        self.assertEqual(self.service._bootstrap_profile_from_rows([{"status": "liked", "movies": {}}])["genres"], {})

    def test_helpers_group_rows_and_count_unique_missing_metadata(self):
        rows = [
            {"user_id": 1, "movie_id": 7, "media_type": "movie", "movies": {"keywords": []}},
            {"user_id": 2, "movie_id": 7, "media_type": "movie", "movies": {"keywords": []}},
        ]
        self.assertEqual(list(group_rows(rows)), [1, 2])
        self.assertEqual(missing_metadata(rows)["titles"], 1)
        self.assertEqual(missing_metadata(rows)["keywords"], 1)


if __name__ == "__main__":
    unittest.main()
