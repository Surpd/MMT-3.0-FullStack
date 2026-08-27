import os
import hmac
import hashlib
import json
import ipaddress
from urllib.parse import parse_qsl
from aiohttp import web
from config import BOT_TOKEN, TV_CRON_SECRET
import logging

logger = logging.getLogger(__name__)

TEST_USER_HEADER = "X-Test-User-Id"
MAX_TEST_USER_ID = 2_000_000_000

def get_init_data_user_id(init_data: str, token: str) -> int | None:
    if not init_data:
        return None
    try:
        parsed_data = dict(parse_qsl(init_data))
        if "hash" not in parsed_data:
            return None
        hash_ = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated_hash, hash_):
            return None
        user_data = json.loads(parsed_data.get("user", "{}"))
        user_id = user_data.get("id")
        return int(user_id) if isinstance(user_id, int) and user_id > 0 else None
    except Exception as e:
        logger.error(f"Auth error: {e}")
        return None


def validate_init_data(init_data: str, token: str) -> bool:
    return get_init_data_user_id(init_data, token) is not None


def _runtime_is_production_like() -> bool:
    return os.getenv("RUNTIME_ENV", "development").strip().lower() in {"production", "staging"}


def _is_loopback(value: str | None) -> bool:
    if not value:
        return False
    value = value.strip().lower()
    if value == "localhost":
        return True
    if value.startswith("[") and "]" in value:
        value = value[1:value.index("]")]
    elif value.count(":") == 1:
        value = value.rsplit(":", 1)[0]
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _request_host(request) -> str:
    host = getattr(request, "host", "") or ""
    if host.startswith("[") and "]" in host:
        return host[1:host.index("]")]
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def _is_local_dev_request(request) -> bool:
    if os.getenv("DEV_MODE", "").strip().lower() != "true" or _runtime_is_production_like():
        return False
    return _is_loopback(getattr(request, "remote", None)) and _is_loopback(_request_host(request))


def _test_auth_enabled() -> bool:
    return os.getenv("TEST_MODE", "").strip().lower() == "true" and not _runtime_is_production_like()


def _parse_test_user_id(value: str | None) -> int | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value.isdecimal() or len(value) > 10:
        return None
    try:
        user_id = int(value)
    except ValueError:
        return None
    return user_id if 0 < user_id <= MAX_TEST_USER_ID else None


def _test_auth_request_allowed(request) -> bool:
    return _test_auth_enabled() and _is_loopback(getattr(request, "remote", None)) and _is_loopback(_request_host(request))

@web.middleware
async def auth_middleware(request, handler):
    # Пропускаем CORS (OPTIONS) и healthcheck (/)
    if request.method == 'OPTIONS' or request.path == '/':
        return await handler(request)

    if request.path == "/api/internal/jobs/tv-notifications":
        expected = f"Bearer {TV_CRON_SECRET}" if TV_CRON_SECRET else ""
        if not expected or not hmac.compare_digest(request.headers.get("Authorization", ""), expected):
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)
        return await handler(request)

    auth_header = request.headers.get("Authorization", "")

    test_user_header = request.headers.get(TEST_USER_HEADER)
    if test_user_header is not None:
        if auth_header:
            return web.json_response({"ok": False, "error": "unauthorized", "reason": "mixed_auth"}, status=401)
        if not _test_auth_request_allowed(request):
            return web.json_response({"ok": False, "error": "unauthorized", "reason": "test_auth_disabled"}, status=401)
        test_user_id = _parse_test_user_id(test_user_header)
        if test_user_id is None:
            return web.json_response({"ok": False, "error": "unauthorized", "reason": "invalid_test_user"}, status=401)
        request["authenticated_user_id"] = test_user_id
        request["local_dev"] = True
        request["test_auth"] = True
        return await handler(request)

    # Локальный режим разработки не должен работать с удаленного адреса.
    # Если клиент прислал Authorization, его всё равно нужно валидировать.
    if not auth_header and _is_local_dev_request(request):
        request["authenticated_user_id"] = None
        request["local_dev"] = True
        return await handler(request)

    if not auth_header.startswith("tma "):
        return web.json_response({"ok": False, "error": "unauthorized", "reason": "missing_header"}, status=401)

    init_data = auth_header[4:] # Отрезаем "tma "
    authenticated_user_id = get_init_data_user_id(init_data, BOT_TOKEN)
    if authenticated_user_id is None:
        return web.json_response({"ok": False, "error": "unauthorized", "reason": "invalid_hash"}, status=401)

    request["authenticated_user_id"] = authenticated_user_id
    request["local_dev"] = False
    return await handler(request)
