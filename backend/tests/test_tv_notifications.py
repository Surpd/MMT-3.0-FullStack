import asyncio
import unittest
from datetime import date
from unittest.mock import AsyncMock, patch

import jobs.refresh_tv_notifications as job
import services.tv_notification_service as service


class FakeDb:
    def __init__(self, delivered=False):
        self.delivered = delivered
        self.marked = []

    async def get_tv_notification_subscriptions(self):
        return [{"user_id": 7, "tv_id": 42}]

    async def has_tv_notification_delivery(self, *_args):
        return self.delivered

    async def mark_tv_notification_delivery(self, *args):
        self.marked.append(args)


class TvNotificationTests(unittest.TestCase):
    def test_failed_send_is_retryable_and_success_is_recorded(self):
        db = FakeDb()
        bot = AsyncMock()
        bot.send_message.side_effect = [RuntimeError("blocked"), None]
        metadata = {"title": "Example", "seasons": 1}
        episodes = [{"episode_number": 1, "air_date": date.today().isoformat(), "name": "Pilot"}]
        with patch.object(job, "db", db), patch.object(job, "bot", bot), patch.object(job, "WEBAPP_URL", "https://example.test"), patch.object(service, "refresh_tv_metadata", AsyncMock(return_value=metadata)), patch.object(service, "load_tv_season", AsyncMock(return_value=episodes)):
            asyncio.run(job.run())
            self.assertEqual(db.marked, [])
            asyncio.run(job.run())
        self.assertEqual(len(db.marked), 1)

    def test_delivered_episode_is_not_sent_again(self):
        db = FakeDb(delivered=True)
        bot = AsyncMock()
        with patch.object(job, "db", db), patch.object(job, "bot", bot), patch.object(service, "refresh_tv_metadata", AsyncMock(return_value={"title": "Example", "seasons": 1})), patch.object(service, "load_tv_season", AsyncMock(return_value=[{"episode_number": 1, "air_date": date.today().isoformat()}])):
            asyncio.run(job.run())
        bot.send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
