import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

os.environ.setdefault("BOT_TOKEN", "test-bot-token")
os.environ.setdefault("TMDB_API_KEY", "test-tmdb-key")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-supabase-key")

from web_app.auth import auth_middleware, get_init_data_user_id, validate_init_data
from web_app.api import _request_user_id


class FakeRequest(dict):
    def __init__(self, headers):
        super().__init__()
        self.method = "GET"
        self.path = "/api/stats"
        self.headers = headers
        self.remote = "127.0.0.1"
        self.host = "127.0.0.1:10000"


def make_init_data(user_id: int, token: str = "test-bot-token") -> str:
    values = {
        "auth_date": "1700000000",
        "user": json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


class AuthTests(unittest.IsolatedAsyncioTestCase):
    def test_request_uses_own_authenticated_identity(self):
        request = FakeRequest(headers={})
        request["authenticated_user_id"] = 123
        request["local_dev"] = False
        self.assertEqual(_request_user_id(request, "123"), 123)

    def test_request_rejects_foreign_user_id(self):
        request = FakeRequest(headers={})
        request["authenticated_user_id"] = 123
        request["local_dev"] = False
        with self.assertRaises(Exception) as raised:
            _request_user_id(request, "456")
        self.assertEqual(raised.exception.status, 403)

    def test_valid_identity_is_extracted(self):
        init_data = make_init_data(123)
        self.assertEqual(get_init_data_user_id(init_data, "test-bot-token"), 123)
        self.assertTrue(validate_init_data(init_data, "test-bot-token"))

    def test_invalid_signature_is_rejected(self):
        self.assertIsNone(get_init_data_user_id(make_init_data(123) + "x", "test-bot-token"))

    def test_malformed_init_data_is_rejected(self):
        self.assertIsNone(get_init_data_user_id("user=%7Bbad%7D&hash=bad", "test-bot-token"))

    async def test_valid_request_exposes_signed_identity(self):
        os.environ.pop("DEV_MODE", None)
        request = FakeRequest(headers={"Authorization": f"tma {make_init_data(123)}"})
        seen = {}

        async def handler(received):
            seen.update(received)
            return "ok"

        with patch("web_app.auth.BOT_TOKEN", "test-bot-token"):
            self.assertEqual(await auth_middleware(request, handler), "ok")
        self.assertEqual(seen["authenticated_user_id"], 123)
        self.assertFalse(seen["local_dev"])

    async def test_missing_auth_is_rejected(self):
        os.environ.pop("DEV_MODE", None)
        request = FakeRequest(headers={})
        async def handler(_):
            return None

        response = await auth_middleware(request, handler)
        self.assertEqual(response.status, 401)

    async def test_dev_mode_is_local_only(self):
        old_value = os.environ.get("DEV_MODE")
        os.environ["DEV_MODE"] = "true"
        try:
            local_request = FakeRequest(headers={})
            async def local_handler(_):
                return None

            await auth_middleware(local_request, local_handler)
            self.assertTrue(local_request["local_dev"])

            remote_request = FakeRequest(headers={})
            remote_request.remote = "203.0.113.10"
            response = await auth_middleware(remote_request, local_handler)
            self.assertEqual(response.status, 401)
        finally:
            if old_value is None:
                os.environ.pop("DEV_MODE", None)
            else:
                os.environ["DEV_MODE"] = old_value

    async def test_test_auth_is_disabled_without_test_mode(self):
        with patch.dict(os.environ, {"TEST_MODE": "false", "RUNTIME_ENV": "development"}, clear=False):
            os.environ.pop("DEV_MODE", None)
            request = FakeRequest(headers={"X-Test-User-Id": "900000001"})
            response = await auth_middleware(request, lambda _: None)
        self.assertEqual(response.status, 401)

    async def test_test_auth_is_disabled_when_test_mode_is_missing(self):
        with patch.dict(os.environ, {"RUNTIME_ENV": "development"}, clear=False):
            os.environ.pop("TEST_MODE", None)
            os.environ.pop("DEV_MODE", None)
            request = FakeRequest(headers={"X-Test-User-Id": "900000001"})
            response = await auth_middleware(request, lambda _: None)
        self.assertEqual(response.status, 401)

    async def test_valid_test_auth_exposes_trusted_identity(self):
        seen = {}

        async def handler(request):
            seen.update(request)
            return "ok"

        with patch.dict(os.environ, {"TEST_MODE": "true", "RUNTIME_ENV": "development"}, clear=False):
            request = FakeRequest(headers={"X-Test-User-Id": "900000001"})
            self.assertEqual(await auth_middleware(request, handler), "ok")
        self.assertEqual(seen["authenticated_user_id"], 900000001)
        self.assertTrue(seen["local_dev"])
        self.assertTrue(seen["test_auth"])

    async def test_invalid_test_user_ids_are_rejected(self):
        with patch.dict(os.environ, {"TEST_MODE": "true", "RUNTIME_ENV": "development"}, clear=False):
            for value in ("", "0", "-1", "1.0", "not-an-id", "2000000001", "12345678901"):
                request = FakeRequest(headers={"X-Test-User-Id": value})
                response = await auth_middleware(request, lambda _: None)
                self.assertEqual(response.status, 401, value)

    async def test_test_auth_is_identity_only_and_cannot_impersonate_foreign_user(self):
        async def handler(request):
            self.assertNotIn("admin", request)
            with self.assertRaises(Exception) as raised:
                _request_user_id(request, "900000002")
            self.assertEqual(raised.exception.status, 403)
            return "ok"

        with patch.dict(os.environ, {"TEST_MODE": "true", "RUNTIME_ENV": "development"}, clear=False):
            request = FakeRequest(headers={"X-Test-User-Id": "900000001"})
            self.assertEqual(await auth_middleware(request, handler), "ok")

    async def test_test_auth_is_disabled_in_production_like_runtime(self):
        with patch.dict(os.environ, {"TEST_MODE": "true", "RUNTIME_ENV": "production"}, clear=False):
            request = FakeRequest(headers={"X-Test-User-Id": "900000001"})
            response = await auth_middleware(request, lambda _: None)
        self.assertEqual(response.status, 401)

    async def test_test_auth_is_restricted_to_loopback(self):
        with patch.dict(os.environ, {"TEST_MODE": "true", "RUNTIME_ENV": "development"}, clear=False):
            request = FakeRequest(headers={"X-Test-User-Id": "900000001"})
            request.remote = "203.0.113.10"
            response = await auth_middleware(request, lambda _: None)
        self.assertEqual(response.status, 401)

    async def test_telegram_auth_still_works_when_test_mode_is_enabled(self):
        async def handler(_):
            return "ok"

        with patch.dict(os.environ, {"TEST_MODE": "true", "RUNTIME_ENV": "development"}, clear=False):
            request = FakeRequest(headers={"Authorization": f"tma {make_init_data(123)}"})
            with patch("web_app.auth.BOT_TOKEN", "test-bot-token"):
                response = await auth_middleware(request, handler)
        self.assertEqual(response, "ok")
        self.assertEqual(request["authenticated_user_id"], 123)

    async def test_invalid_telegram_auth_is_not_replaced_by_test_auth(self):
        with patch.dict(os.environ, {"TEST_MODE": "true", "RUNTIME_ENV": "development"}, clear=False):
            request = FakeRequest(headers={"Authorization": "tma invalid"})
            response = await auth_middleware(request, lambda _: None)
        self.assertEqual(response.status, 401)


if __name__ == "__main__":
    unittest.main()
