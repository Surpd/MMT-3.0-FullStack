import unittest
import asyncio
from unittest.mock import AsyncMock, patch
from datetime import date, timedelta

import services.tv_service as tv_service
from services.tv_service import _is_released, choose_next_episode, compute_tv_state, is_tv_metadata_complete


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
                return {
                    "id": 42,
                    "media_type": "tv",
                    "seasons": 1,
                    "metadata_updated_at": date.today().isoformat() + "T00:00:00+00:00",
                }

            async def get_tv_seasons(self, _tv_id):
                return [{"season_number": 1, "episode_count": 1}]

            async def get_tv_episodes_for_tv(self, _tv_id):
                return [{"season_number": 1, "episode_number": 1, "air_date": date.today().isoformat()}]

        with patch.object(tv_service, "db", FakeDb()), patch.object(tv_service.tmdb, "get_tv_details_extended", AsyncMock(side_effect=AssertionError)):
            result = asyncio.run(tv_service.refresh_tv_metadata(42))
        self.assertEqual(result["id"], 42)

    def test_season_cache_reuse_avoids_tmdb_request(self):
        cached = [{"episode_number": 1, "metadata_updated_at": date.today().isoformat() + "T00:00:00+00:00"}]

        class FakeDb:
            async def get_tv_episodes(self, _tv_id, _season):
                return cached

            async def get_tv_seasons(self, _tv_id):
                return [{"season_number": 1, "episode_count": 1}]

        with patch.object(tv_service, "db", FakeDb()), patch.object(tv_service.tmdb, "get_tv_season_details", AsyncMock(side_effect=AssertionError)):
            result = asyncio.run(tv_service.load_tv_season(42, 1))
        self.assertEqual(result, cached)

    def test_batch_progress_summary_counts_released_episodes_only(self):
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        class FakeDb:
            async def get_tv_seasons_for_tv_ids(self, _tv_ids):
                return [{"tv_id": 42, "season_number": 1, "episode_count": 3}]

            async def get_tv_episodes_for_tv_ids(self, _tv_ids):
                return [
                    {"tv_id": 42, "season_number": 1, "episode_number": 1, "air_date": today},
                    {"tv_id": 42, "season_number": 1, "episode_number": 2, "air_date": today},
                    {"tv_id": 42, "season_number": 1, "episode_number": 3, "air_date": tomorrow},
                ]

            async def get_user_episode_progress_for_tv_ids(self, _user_id, _tv_ids):
                return [{"tv_id": 42, "season_number": 1, "episode_number": 1}]

            async def get_movie(self, _tv_id, _media_type):
                return {"seasons": 1}

        with patch.object(tv_service, "db", FakeDb()), patch.object(
            tv_service, "refresh_tv_metadata", AsyncMock(return_value={"seasons": 1})
        ):
            result = asyncio.run(tv_service.get_tv_progress_summaries(7, [42]))[42]

        self.assertEqual(result["watched_episodes"], 1)
        self.assertEqual(result["available_episodes"], 2)
        self.assertEqual(result["next_episode"]["episode_number"], 2)
        self.assertEqual(result["state"], "watching")

    def test_library_summary_can_use_cached_metadata_without_refresh_or_n_plus_one(self):
        today = date.today().isoformat()

        class FakeDb:
            async def get_tv_seasons_for_tv_ids(self, _tv_ids):
                return [{"tv_id": 42, "season_number": 1, "episode_count": 1}]

            async def get_tv_episodes_for_tv_ids(self, _tv_ids):
                return [{"tv_id": 42, "season_number": 1, "episode_number": 1, "air_date": today}]

            async def get_user_episode_progress_for_tv_ids(self, _user_id, _tv_ids):
                return []

            async def get_movie(self, *_args):
                raise AssertionError("library summaries should use joined metadata")

        with patch.object(tv_service, "db", FakeDb()), patch.object(
            tv_service, "refresh_tv_metadata", AsyncMock(side_effect=AssertionError)
        ):
            result = asyncio.run(
                tv_service.get_tv_progress_summaries(
                    7,
                    [42],
                    ensure_metadata=False,
                    metadata_by_tv_id={42: {"seasons": 1}},
                )
            )[42]

        self.assertEqual(result["available_episodes"], 1)
        self.assertEqual(result["watched_episodes"], 0)

    def test_metadata_completeness_counts_all_seasons_and_excludes_specials(self):
        seasons = [
            {"season_number": 0, "episode_count": 2},
            {"season_number": 1, "episode_count": 10},
            {"season_number": 2, "episode_count": 8},
            {"season_number": 3, "episode_count": 12},
        ]
        episodes = [
            {"season_number": season, "episode_number": episode}
            for season, count in ((0, 2), (1, 10), (2, 8), (3, 12))
            for episode in range(1, count + 1)
        ]
        self.assertTrue(is_tv_metadata_complete({"seasons": 3}, seasons, episodes))

    def test_metadata_completeness_rejects_partial_catalog_and_future_episodes_are_not_available(self):
        seasons = [
            {"season_number": 1, "episode_count": 10},
            {"season_number": 2, "episode_count": 8},
            {"season_number": 3, "episode_count": 12},
        ]
        partial = [{"season_number": 1, "episode_number": index} for index in range(1, 11)]
        self.assertFalse(is_tv_metadata_complete({"seasons": 3}, seasons, partial))
        self.assertFalse(is_tv_metadata_complete({"seasons": 3}, seasons[1:], partial))

        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(
            sum(_is_released(row.get("air_date")) for row in [
                {"air_date": today},
                {"air_date": tomorrow},
            ]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
