from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import db


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