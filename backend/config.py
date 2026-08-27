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
from services.quiz_service import QuizPoolService

load_dotenv(override=False)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "") # <--- ДОБАВИЛИ ЭТО
REDIS_URL = os.getenv("REDIS_URL", "")
RUNTIME_ENV = os.getenv("RUNTIME_ENV", "development").lower()
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8000")
TV_CRON_SECRET = os.getenv("TV_CRON_SECRET", "")
TEST_MODE = os.getenv("TEST_MODE", "false").strip().lower() == "true"
TEST_USER_ID = os.getenv("TEST_USER_ID", "900000001").strip()

if TEST_MODE and RUNTIME_ENV in {"production", "staging"}:
    raise RuntimeError("TEST_MODE cannot be enabled in production-like runtime")
if TEST_MODE:
    test_supabase_url = os.getenv("TEST_SUPABASE_URL", "").strip()
    test_supabase_key = os.getenv("TEST_SUPABASE_KEY", "").strip()
    if not test_supabase_url or not test_supabase_key:
        raise RuntimeError("TEST_SUPABASE_URL and TEST_SUPABASE_KEY are required when TEST_MODE=true")
    if test_supabase_url == os.getenv("SUPABASE_URL", "").strip():
        raise RuntimeError("TEST_SUPABASE_URL must differ from SUPABASE_URL")
    SUPABASE_URL = test_supabase_url
    SUPABASE_KEY = test_supabase_key
if TEST_MODE and (
    not TEST_USER_ID.isdecimal() or len(TEST_USER_ID) > 10 or not 0 < int(TEST_USER_ID) <= 2_000_000_000
):
    raise RuntimeError("TEST_USER_ID must be a positive integer <= 2000000000")

if RUNTIME_ENV in {"production", "staging"} and (
    not os.getenv("WEBAPP_URL")
    or os.getenv("WEBAPP_URL", "").startswith(("http://localhost", "http://127.0.0.1"))
):
    raise RuntimeError("WEBAPP_URL is required outside development")

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
daily_cache = MemoryCache(ttl_sec=48 * 60 * 60)
recs_pool_cache = MemoryCache(ttl_sec=2 * 60 * 60)
quiz_pool_cache = MemoryCache(ttl_sec=20 * 60)
db = SupabaseDatabase(url=SUPABASE_URL, key=SUPABASE_KEY)

quiz_pool_service = QuizPoolService(db=db, tmdb=tmdb, cache=quiz_pool_cache)

recommendation_service = RecommendationService(
    db=db,
    tmdb=tmdb,
    session_cache=session_cache,
    recs_pool_cache=recs_pool_cache
)
