import asyncio
import unittest

from services.media_state_service import apply_media_state


class _Db:
    def __init__(self):
        self.row = None
        self.writes = 0

    async def get_user_movie(self, *_args):
        return self.row

    async def upsert_user_movie(self, **kwargs):
        self.writes += 1
        self.row = type("Row", (), {"status": kwargs["status"], "action_id": kwargs.get("action_id")})()


class _Recommendations:
    def __init__(self):
        self.updates = 0
        self.invalidations = 0

    async def update_taste_profile(self, *_args):
        self.updates += 1

    async def rebuild_taste_profile(self, *_args):
        self.updates += 1

    async def invalidate_user_cache(self, *_args):
        self.invalidations += 1


class MediaStateServiceTests(unittest.TestCase):
    def test_same_action_id_is_idempotent(self):
        db = _Db()
        recommendations = _Recommendations()
        first = asyncio.run(apply_media_state(db, recommendations, 7, 10, "movie", "liked", action_id="a1"))
        second = asyncio.run(apply_media_state(db, recommendations, 7, 10, "movie", "liked", action_id="a1"))
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(db.writes, 1)
        self.assertEqual(recommendations.updates, 1)

    def test_repeated_state_without_action_id_is_a_noop(self):
        db = _Db()
        recommendations = _Recommendations()
        asyncio.run(apply_media_state(db, recommendations, 7, 10, "movie", "liked"))
        result = asyncio.run(apply_media_state(db, recommendations, 7, 10, "movie", "liked"))
        self.assertTrue(result["duplicate"])
        self.assertEqual(db.writes, 1)
        self.assertEqual(recommendations.updates, 1)

    def test_positive_status_transition_rebuilds_instead_of_counting_again(self):
        db = _Db()
        recommendations = _Recommendations()
        asyncio.run(apply_media_state(db, recommendations, 7, 10, "movie", "liked"))
        asyncio.run(apply_media_state(db, recommendations, 7, 10, "movie", "watchlist"))
        self.assertEqual(db.writes, 2)
        self.assertEqual(recommendations.updates, 2)


if __name__ == "__main__":
    unittest.main()
