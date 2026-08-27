import unittest

from models.movie_model import MovieModel


class MovieModelGenreTests(unittest.TestCase):
    def test_known_tv_genre_ids_are_labeled_and_unknown_ids_are_ignored(self):
        movie = MovieModel.from_dict(
            {
                "movie_id": 1,
                "title": "Example",
                "genre_ids": [10765, 999999],
                "media_type": "tv",
            }
        )

        self.assertEqual(movie.genre_names, ["Фантастика и фэнтези"])

    def test_normal_genre_names_are_preserved(self):
        movie = MovieModel.from_dict(
            {"movie_id": 2, "title": "Example", "genres_array": ["Криминал", "Drama"]}
        )

        self.assertEqual(movie.genre_names, ["Криминал", "Drama"])


if __name__ == "__main__":
    unittest.main()
