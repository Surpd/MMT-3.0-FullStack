from aiogram.types import InlineKeyboardMarkup

from config import WEBAPP_URL
from services.telegram_ui import build_movie_keyboard

def movie_card_keyboard(movie_id, user_status, media_type="movie", user_rating=None, back_data=None, details_btn_text="ℹ️ Детали", is_full: bool = False):
    return build_movie_keyboard(
        movie_id=int(movie_id), user_status=user_status or "none", media_type=media_type,
        user_rating=user_rating, back_data=back_data, webapp_url=WEBAPP_URL,
    )
