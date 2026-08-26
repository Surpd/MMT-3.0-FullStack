import json
import unittest
from unittest.mock import AsyncMock, patch

from web_app.api import handle_tv_notifications_job
from web_app.auth import auth_middleware


class FakeRequest(dict):
    def __init__(self, headers):
        super().__init__()
        self.method = "POST"
        self.path = "/api/internal/jobs/tv-notifications"
        self.headers = headers
        self.remote = "198.51.100.10"
        self.host = "mmt-3-0-fullstack.onrender.com"


class TvInternalEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_and_wrong_secret_are_rejected(self):
        async def handler(_):
            self.fail("unauthorized request reached handler")

        with patch("web_app.auth.TV_CRON_SECRET", "cron-test-secret"):
            for headers in ({}, {"Authorization": "Bearer wrong"}):
                response = await auth_middleware(FakeRequest(headers), handler)
                self.assertEqual(response.status, 401)

    async def test_valid_secret_runs_scan_without_user_input(self):
        summary = {"ok": True, "busy": False, "subscriptions_checked": 0, "shows_checked": 0, "notifications_sent": 0, "failures": 0}
        request = FakeRequest({"Authorization": "Bearer cron-test-secret"})
        with patch("web_app.auth.TV_CRON_SECRET", "cron-test-secret"), patch(
            "web_app.api.run_tv_notification_scan", AsyncMock(return_value=summary)
        ) as scan:
            response = await auth_middleware(request, handle_tv_notifications_job)
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.text), summary)
        scan.assert_awaited_once()

    async def test_busy_scan_returns_conflict(self):
        request = FakeRequest({"Authorization": "Bearer cron-test-secret"})
        summary = {"ok": False, "busy": True, "subscriptions_checked": 0, "shows_checked": 0, "notifications_sent": 0, "failures": 0}
        with patch("web_app.auth.TV_CRON_SECRET", "cron-test-secret"), patch(
            "web_app.api.run_tv_notification_scan", AsyncMock(return_value=summary)
        ):
            response = await auth_middleware(request, handle_tv_notifications_job)
        self.assertEqual(response.status, 409)


if __name__ == "__main__":
    unittest.main()
