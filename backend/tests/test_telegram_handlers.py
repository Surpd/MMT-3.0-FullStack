import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

from aiogram.exceptions import TelegramBadRequest

from handlers.movie import cb_compact_rating
from handlers.series import _edit_screen, _show_series


class TelegramHandlerRegressionTests(unittest.TestCase):
    def test_rating_is_saved_when_metadata_refresh_fails(self):
        callback = SimpleNamespace(
            data="rate:movie:42:5",
            from_user=SimpleNamespace(id=7),
            message=SimpleNamespace(chat=SimpleNamespace(id=7)),
            answer=AsyncMock(),
        )

        with patch("handlers.movie.ensure_movie_in_db", AsyncMock(side_effect=RuntimeError("TMDB unavailable"))), \
                patch("handlers.movie.apply_rating", AsyncMock()) as save_rating, \
                patch("handlers.movie.render_and_send_card", AsyncMock()):
            asyncio.run(cb_compact_rating(callback))

        save_rating.assert_awaited_once_with(
            ANY,
            ANY,
            7,
            42,
            "movie",
            5,
        )
        self.assertIn("Оценка сохранена", callback.answer.await_args.args[0])

    def test_series_screen_ignores_repeated_identical_edit(self):
        message = SimpleNamespace(
            photo=None,
            edit_text=AsyncMock(
                side_effect=TelegramBadRequest(
                    method="editMessageText",
                    message="message is not modified",
                )
            ),
        )

        asyncio.run(_edit_screen(message, "Экран", None))
        message.edit_text.assert_awaited_once()

    def test_continue_screen_includes_saved_series_not_started_yet(self):
        message = SimpleNamespace(from_user=SimpleNamespace(id=7))
        edit_screen = AsyncMock()
        with patch("handlers.series._tv_ids", AsyncMock(return_value=[42])), \
                patch("handlers.series.get_tv_progress_summaries", AsyncMock(return_value={
                    42: {
                        "title": "Рим",
                        "state": "none",
                        "known_episodes": 22,
                        "available_episodes": 22,
                        "watched_episodes": 0,
                    }
                })), \
                patch("handlers.series._edit_screen", edit_screen):
            asyncio.run(_show_series(message, continue_only=True, edit_message=message))

        _, text, markup = edit_screen.await_args.args
        callbacks = [
            (button.callback_data, button.text)
            for row in markup.inline_keyboard
            for button in row
            if button.callback_data
        ]
        self.assertTrue(any(callback == "tv:42" and "Рим" in label for callback, label in callbacks))


if __name__ == "__main__":
    unittest.main()
