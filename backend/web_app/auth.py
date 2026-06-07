import os
import hmac
import hashlib
from urllib.parse import parse_qsl
from aiohttp import web
from config import BOT_TOKEN
import logging

logger = logging.getLogger(__name__)

def validate_init_data(init_data: str, token: str) -> bool:
    if not init_data:
        return False
    try:
        parsed_data = dict(parse_qsl(init_data))
        if "hash" not in parsed_data:
            return False
        hash_ = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return calculated_hash == hash_
    except Exception as e:
        logger.error(f"Auth error: {e}")
        return False

@web.middleware
async def auth_middleware(request, handler):
    # Пропускаем CORS (OPTIONS) и healthcheck (/)
    if request.method == 'OPTIONS' or request.path == '/':
        return await handler(request)

    auth_header = request.headers.get("Authorization", "")
    
    # Режим разработчика (если открываешь просто в браузере на ПК)
    if os.getenv("DEV_MODE") == "true":
        return await handler(request)

    if not auth_header.startswith("tma "):
        return web.json_response({"ok": False, "error": "unauthorized", "reason": "missing_header"}, status=401)

    init_data = auth_header[4:] # Отрезаем "tma "
    if not validate_init_data(init_data, BOT_TOKEN):
        return web.json_response({"ok": False, "error": "unauthorized", "reason": "invalid_hash"}, status=401)

    return await handler(request)