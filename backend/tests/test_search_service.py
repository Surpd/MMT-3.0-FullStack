import unittest

from services.search_service import _parse_ai_movies, _pick_ai_match
from services.tmdb import MovieSearchResult


class SearchHardeningTests(unittest.TestCase):
    def test_ai_payload_is_bounded_validated_and_deduplicated(self):
        content = '{"movies":[{"title":"A","year":2020},{"title":"A","year":2020},{"title":"bad","year":"not-year"},{"title":"B","year":2021}]} trailing'
        self.assertEqual(_parse_ai_movies(content), [{"title": "A", "year": 2020}, {"title": "B", "year": 2021}])

    def test_ai_match_rejects_year_mismatch(self):
        items = [
            MovieSearchResult(movie_id=1, title="Wrong", year="2019"),
            MovieSearchResult(movie_id=2, title="Right", year="2020"),
        ]
        self.assertEqual(_pick_ai_match(items, {"title": "Right", "year": 2020}).movie_id, 2)
        self.assertIsNone(_pick_ai_match(items, {"title": "Right", "year": 2021}))


if __name__ == "__main__":
    unittest.main()
