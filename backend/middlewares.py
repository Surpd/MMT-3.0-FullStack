import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import db

RATE_LIMIT_SECONDS = 1.0


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
 # Находим пользователя в событии (сообщении или нажатии кнопки)
        user = None
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user

        if user is not None:
            # Передаем всё: ID, никнейм и имя
            await db.ensure_user(
                user_id=user.id, 
                username=user.username, 
                first_name=user.first_name
            )

        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._last_request: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user

        if user:
            # --- ЗАЩИТА ОТ ОГРОМНЫХ ТЕКСТОВ ---
            if isinstance(event, Message) and event.text:
                if len(event.text) > 150:
                    try:
                        await event.answer("⛔️ Слишком длинный текст. Напиши короче!")
                    except Exception:
                        pass
                    return
            # ----------------------------------

            now = time.time()
            last = self._last_request.get(user.id, 0)
            if now - last < RATE_LIMIT_SECONDS:
                return
            self._last_request[user.id] = now

        return await handler(event, data)