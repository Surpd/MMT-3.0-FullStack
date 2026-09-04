import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from config import db, WEBAPP_URL
from keyboards.main_kb import main_menu_keyboard
from services.ui import render_and_send_card
from utils.templates import EMPTY_WISH_TEXT

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.ensure_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    await message.answer(
        f"Привет, {html.escape(message.from_user.first_name or 'друг')}! 🎬\nПрофиль загружен. Выбирай, что будем делать дальше:",
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
@router.message(F.text.in_({"🌐 Открыть приложение"}))
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


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Команды:\n/search — найти фильм, сериал или человека\n/recommend — рекомендации\n/library — библиотека\n/series — сериалы и прогресс\n/profile — профиль\n/app — открыть Mini App",
        reply_markup=main_menu_keyboard(),
    )



