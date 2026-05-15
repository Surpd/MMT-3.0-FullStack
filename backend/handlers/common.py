import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from config import db
from keyboards.main_kb import main_menu_keyboard
from services.ui import render_and_send_card
from utils.templates import EMPTY_WISH_TEXT

router = Router()
WEBAPP_URL = "https://film-fling-flow.lovable.app"

@router.message(Command("start"))
async def cmd_start(message: Message):
    await db.ensure_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    await message.answer(
        f"Привет, {message.from_user.first_name}! 🎬\nПрофиль загружен. Выбирай, что будем делать дальше:",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("refresh"))
async def cmd_refresh(message: Message):
    await message.answer("Обновляю интерфейс...", reply_markup=ReplyKeyboardRemove())

    await message.answer(
        "Меню обновлено! 🎬",
        reply_markup=main_menu_keyboard(),
    )

@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎬 Открыть Mini App",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        ]
    )
    await message.answer("Открой Mini App для свайпов и галереи:", reply_markup=markup)



