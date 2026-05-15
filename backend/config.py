import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Убрали импорт DatabaseCRUD
from services.database import SupabaseDatabase
from services.tmdb import TMDBClient
from services.cache import MemoryCache
from services.recommendation_service import RecommendationService

load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

if not all([BOT_TOKEN, TMDB_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
    raise RuntimeError("Missing env vars: BOT_TOKEN, TMDB_API_KEY, SUPABASE_URL, SUPABASE_KEY")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

tmdb = TMDBClient(api_key=TMDB_API_KEY, language="ru-RU", timeout_sec=30)
search_cache = MemoryCache(ttl_sec=10 * 60)
movie_cache = MemoryCache(ttl_sec=24 * 60 * 60)
# Оставляем только ЕДИНУЮ точку входа для базы
session_cache = MemoryCache(ttl_sec=60 * 60)       
recs_pool_cache = MemoryCache(ttl_sec=2 * 60 * 60)
db = SupabaseDatabase(url=SUPABASE_URL, key=SUPABASE_KEY)

recommendation_service = RecommendationService(
    db=db,
    tmdb=tmdb,
    session_cache=session_cache,
    recs_pool_cache=recs_pool_cache
)