import unittest
from datetime import date, timedelta

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


if __name__ == "__main__":
    unittest.main()
