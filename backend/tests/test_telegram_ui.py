import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services.search_service import get_person_search_results, get_typed_search_results, get_unified_search_results
from services.cards import CardFormatter
from services.telegram_ui import build_library_page, build_movie_keyboard, parse_callback, render_movie_message
from services.tmdb import MovieSearchResult
from keyboards.search_kb import get_search_results_kb
from keyboards.main_kb import main_menu_keyboard
from services.series_tracking_service import build_progress_bar, render_tracked_series_page


class TelegramUiTests(unittest.TestCase):
    def test_callback_parser_accepts_compact_movie_action(self):
        self.assertEqual(parse_callback("a:watchlist:movie:12345").args, ("watchlist", "movie", "12345"))
        self.assertEqual(parse_callback("sm:movie:12345").name, "search_movie")
        self.assertEqual(parse_callback("libm:tv:123:liked:0:all").name, "library_movie")

    def test_callback_parser_rejects_malformed_or_oversized_data(self):
        self.assertIsNone(parse_callback("a:watchlist:movie:not-a-number"))
        self.assertIsNone(parse_callback("x:" + "a" * 70))
        self.assertIsNone(parse_callback("rate:movie:1:9"))

    def test_movie_keyboard_has_watched_rating_watchlist_and_dislike_actions(self):
        markup = build_movie_keyboard(42, "none", "movie")
        callbacks = [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]
        self.assertIn("a:liked:movie:42", callbacks)
        self.assertIn("a:watchlist:movie:42", callbacks)
        self.assertIn("a:archive:movie:42", callbacks)
        self.assertIn("ratepick:movie:42", callbacks)

    def test_movie_keyboard_changes_actions_for_watchlist_and_watched(self):
        watchlist = [button.callback_data for row in build_movie_keyboard(42, "watchlist", "tv").inline_keyboard for button in row if button.callback_data]
        watched = [button.callback_data for row in build_movie_keyboard(42, "liked", "movie").inline_keyboard for button in row if button.callback_data]
        self.assertIn("a:liked:tv:42", watchlist)
        self.assertIn("a:none:tv:42", watchlist)
        self.assertIn("a:watchlist:movie:42", watched)

    def test_card_keeps_return_context(self):
        callbacks = [button.callback_data for row in build_movie_keyboard(42, "none", "movie", back_data="s:all:1").inline_keyboard for button in row if button.callback_data]
        self.assertIn("detail:movie:42:s:all:1", callbacks)

    def test_search_result_uses_search_context_and_previous_page(self):
        markup = get_search_results_kb([MovieSearchResult(42, "Film", "2020", "movie")], 2, "all")
        callbacks = [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]
        self.assertIn("sm:movie:42", callbacks)
        self.assertIn("s:all:1", callbacks)

    def test_rating_callback_is_allowlisted(self):
        self.assertEqual(parse_callback("rate:movie:42:5").name, "rate")
        self.assertIsNone(parse_callback("rate:movie:42:0"))

    def test_rendering_is_bounded_and_html_safe(self):
        text = render_movie_message({"id": 1, "title": "A < B", "year": "2020", "overview": "x" * 5000}, full=False)
        self.assertLessEqual(len(text), 4000)
        self.assertIn("A &lt; B", text)

    def test_photo_caption_escapes_tmdb_special_characters(self):
        package = CardFormatter.get_card_package(
            {"id": 1, "title": "A & B < C > _ * [ ] ( ) `", "year": "2020", "overview": "& < > _ * [ ] ( ) `"},
            "movie",
        )
        self.assertIn("A &amp; B &lt; C &gt;", package["caption"])
        self.assertIn("_ * [ ] ( ) `", package["caption"])
        self.assertLessEqual(len(package["caption"]), 1024)

    def test_library_pagination(self):
        page, number, has_previous, has_next = build_library_page(list(range(12)), 1, 5)
        self.assertEqual(page, [5, 6, 7, 8, 9])
        self.assertEqual((number, has_previous, has_next), (1, True, True))

    def test_library_last_page_has_no_next(self):
        page, _, previous, next_page = build_library_page(list(range(10)), 1, 5)
        self.assertEqual(page, [5, 6, 7, 8, 9])
        self.assertTrue(previous)
        self.assertFalse(next_page)

    def test_typed_movie_search_filters_tv_results(self):
        fake = SimpleNamespace(search_movies=AsyncMock(return_value=[
            MovieSearchResult(1, "Film", "2020", "movie"),
            MovieSearchResult(2, "Show", "2020", "tv"),
        ]))
        with patch("services.search_service.tmdb", fake):
            result, _ = asyncio.run(get_typed_search_results("q", "movie"))
        self.assertEqual([item.movie_id for item in result], [1])

    def test_person_search_flow_returns_bounded_results(self):
        fake = SimpleNamespace(search_people=AsyncMock(return_value=[{"id": index, "name": f"P{index}"} for index in range(10)]))
        with patch("services.search_service.tmdb", fake):
            result, _ = asyncio.run(get_person_search_results("Nolan"))
        self.assertEqual(len(result), 5)

    def test_unified_search_uses_one_multi_search_result_set(self):
        fake = SimpleNamespace(search_all=AsyncMock(return_value=[
            MovieSearchResult(1, "Film", "2020", "movie"),
            {"id": 2, "name": "Christopher Nolan", "media_type": "person"},
        ]))
        with patch("services.search_service.tmdb", fake):
            result, source = asyncio.run(get_unified_search_results("Nolan"))
        self.assertEqual(len(result), 2)
        self.assertEqual(source, "🔍 TMDB")

    def test_recommendation_action_parser_and_next_protocol(self):
        action = parse_callback("recact:archive:tv:77")
        self.assertEqual(action.name, "recommendation_action")
        self.assertEqual(parse_callback("rec:next").args, ("next",))

    def test_filter_parser_keeps_hard_filter_values(self):
        self.assertEqual(parse_callback("rf:rating:8.5").args, ("rating", "8.5"))
        self.assertEqual(parse_callback("rf:type:tv").args, ("type", "tv"))
        self.assertIsNone(parse_callback("rf:rating:5"))

    def test_tv_episode_and_subscription_callbacks_are_safe(self):
        self.assertEqual(parse_callback("ep:42:2:5:1").name, "episode")
        self.assertEqual(parse_callback("ep:42:2:5:0").args[-1], "0")
        self.assertEqual(parse_callback("sub:42").name, "subscription")

    def test_unified_search_pagination_and_season_callbacks_are_supported(self):
        self.assertEqual(parse_callback("s:all:2").args, ("all", "2"))
        self.assertEqual(parse_callback("season:42:2").name, "season")
        self.assertEqual(parse_callback("season:42:2:3").args, ("42", "2", "3"))
        self.assertEqual(parse_callback("detail:movie:42:s:all:1").args, ("movie", "42", "s:all:1"))
        self.assertEqual(parse_callback("detail:movie:42:rec:nav:0").args, ("movie", "42", "rec:nav:0"))
        self.assertIsNone(parse_callback("season:42:0"))

    def test_tracked_series_callbacks_and_progress_rendering(self):
        self.assertEqual(parse_callback("tracked:2").args, ("2",))
        self.assertEqual(parse_callback("tv:42:tracked").args, ("progress", "42", "tracked"))
        self.assertEqual(build_progress_bar(5, 10), "█████░░░░░")
        text = render_tracked_series_page([
            {"title": "Рим", "watched_episodes": 5, "available_episodes": 10,
             "next_episode": {"season_number": 1, "episode_number": 6, "name": "Фортуна"}}
        ], 1, 1)
        self.assertIn("Рим", text)
        self.assertIn("5 из 10", text)
        self.assertIn("S01E06", text)

    def test_main_menu_keeps_core_sections_without_separate_series_tab(self):
        labels = [
            button.text
            for row in main_menu_keyboard().keyboard
            for button in row
        ]
        self.assertIn("📚 Моё", labels)
        self.assertIn("🧠 Квиз", labels)
        self.assertNotIn("📺 Сериалы", labels)


if __name__ == "__main__":
    unittest.main()
