import unittest
import asyncio
from unittest.mock import AsyncMock, patch
from datetime import date, timedelta

import services.tv_service as tv_service
from services.tv_service import _is_released, choose_next_episode, compute_tv_state


class TvServiceTests(unittest.TestCase):
    def test_future_episode_is_not_released(self):
        self.assertFalse(_is_released((date.today() + timedelta(days=1)).isoformat()))
        self.assertTrue(_is_released(date.today().isoformat()))

    def test_next_episode_skips_watched_and_future(self):
        episodes = [
            {"season_number": 2, "episode_number": 4, "air_date": date.today().isoformat()},
            {"season_number": 2, "episode_number": 5, "air_date": (date.today() + timedelta(days=1)).isoformat()},
            {"season_number": 2, "episode_number": 6, "air_date": date.today().isoformat()},
        ]
        self.assertEqual(choose_next_episode(episodes, {(2, 4)})["episode_number"], 6)

    def test_tv_states_distinguish_watching_caught_up_and_completed(self):
        self.assertEqual(compute_tv_state("watchlist", 0, 8, "Returning Series"), "watchlist")
        self.assertEqual(compute_tv_state("watchlist", 2, 8, "Returning Series"), "watching")
        self.assertEqual(compute_tv_state("watchlist", 8, 8, "Returning Series"), "caught_up")
        self.assertEqual(compute_tv_state("watchlist", 8, 8, "Ended"), "completed")

    def test_metadata_ttl_avoids_tmdb_request(self):
        class FakeDb:
            async def get_movie(self, _tv_id):
                return {"id": 42, "media_type": "tv", "metadata_updated_at": date.today().isoformat() + "T00:00:00+00:00"}

        with patch.object(tv_service, "db", FakeDb()), patch.object(tv_service.tmdb, "get_tv_details_extended", AsyncMock(side_effect=AssertionError)):
            result = asyncio.run(tv_service.refresh_tv_metadata(42))
        self.assertEqual(result["id"], 42)

    def test_season_cache_reuse_avoids_tmdb_request(self):
        cached = [{"episode_number": 1, "metadata_updated_at": date.today().isoformat() + "T00:00:00+00:00"}]

        class FakeDb:
            async def get_tv_episodes(self, _tv_id, _season):
                return cached

        with patch.object(tv_service, "db", FakeDb()), patch.object(tv_service.tmdb, "get_tv_season_details", AsyncMock(side_effect=AssertionError)):
            result = asyncio.run(tv_service.load_tv_season(42, 1))
        self.assertEqual(result, cached)


if __name__ == "__main__":
    unittest.main()
