import asyncio
import unittest

from database.crud import DatabaseCRUD
from services.recommendation_service import RecommendationService


class FakeQuery:
    def __init__(self, result=None):
        self.result = result

    def execute(self):
        return self.result


class FakeMoviesTable:
    def __init__(self):
        self.upsert_calls = []

    def upsert(self, payload, on_conflict=None):
        self.upsert_calls.append((payload, on_conflict))
        return FakeQuery()


class FakeClient:
    def __init__(self):
        self.movies = FakeMoviesTable()

    def table(self, name):
        if name == "movies":
            return self.movies
        raise AssertionError(f"unexpected table: {name}")


class DataAccessTests(unittest.TestCase):
    def test_save_movie_performs_one_upsert(self):
        crud = DatabaseCRUD.__new__(DatabaseCRUD)
        fake_client = FakeClient()
        crud._client = fake_client

        asyncio.run(crud.save_movie({"id": 10, "title": "Test", "media_type": "movie"}))

        self.assertEqual(len(fake_client.movies.upsert_calls), 1)
        self.assertEqual(fake_client.movies.upsert_calls[0][1], "id")

    def test_rating_signal_preserves_status_but_changes_strength(self):
        service = RecommendationService(None, None, None, None)
        self.assertEqual(service._rating_signal(1), -1.0)
        self.assertEqual(service._rating_signal(3), 0.0)
        self.assertEqual(service._rating_signal(5), 0.5)


if __name__ == "__main__":
    unittest.main()
