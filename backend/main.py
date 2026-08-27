import asyncio
import logging
import os
from aiohttp import web
from config import bot, dp, tmdb, TEST_MODE

# Импортируем наши чистые API обработчики
from web_app.api import (
    handle_get_movies,
    handle_get_recommendations,
    handle_swipe, 
    handle_set_rating,
    handle_get_library, 
    handle_search,
    handle_get_movie_details,
    handle_get_stats,
    handle_get_quiz,
    handle_get_quiz_meta,
    handle_quiz_prewarm,
    handle_quiz_complete,
    handle_quiz_answer,
    handle_get_search_tags,
    handle_get_taste_summary,
    handle_get_tv_progress,
    handle_get_tv_season,
    handle_set_tv_episode_progress,
    handle_set_tv_season_progress,
    handle_set_tv_notifications,
    handle_tv_notifications_job,
)

# Роутеры бота (оставляем как было)
from handlers.common import router as common_router
from handlers.library import router as library_router
from handlers.search import router as search_router
from handlers.quiz import router as quiz_router
from handlers.movie import router as movie_router
from handlers.recommendations import router as recommendations_router
from handlers.stats import router as stats_router
from web_app.auth import auth_middleware
from middlewares import ThrottlingMiddleware, UserMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("movie_tracker_bot")

dp.message.middleware(ThrottlingMiddleware())
dp.callback_query.middleware(ThrottlingMiddleware())
dp.message.middleware(UserMiddleware())
dp.callback_query.middleware(UserMiddleware())

dp.include_router(common_router)
dp.include_router(library_router)
dp.include_router(quiz_router)
dp.include_router(movie_router)
dp.include_router(recommendations_router)
dp.include_router(stats_router)
dp.include_router(search_router)

# CORS Middleware (нужен, чтобы браузер не ругался)
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        response = web.Response()
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
    
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Test-User-Id, ngrok-skip-browser-warning'
    return response

async def health_check(request):
    return web.Response(text="Bot and API are alive! 🚀")

async def start_web_server():
    if TEST_MODE:
        logger.warning("TEST AUTH ENABLED: loopback test requests only")
    app = web.Application(middlewares=[cors_middleware, auth_middleware])
    app.router.add_get('/', health_check)
    
    # === РЕГИСТРАЦИЯ МАРШРУТОВ ИЗ API.PY ===
    app.router.add_get('/api/movies', handle_get_movies)
    app.router.add_get('/api/recommendations', handle_get_recommendations)
    app.router.add_post('/api/swipe', handle_swipe)
    app.router.add_post('/api/rate', handle_set_rating)
    app.router.add_get('/api/library', handle_get_library)
    app.router.add_get('/api/search', handle_search)
    app.router.add_get('/api/movie', handle_get_movie_details)
    app.router.add_get('/api/movie-details', handle_get_movie_details)
    app.router.add_get('/api/stats', handle_get_stats)
    app.router.add_get('/api/quiz', handle_get_quiz)
    app.router.add_get('/api/quiz/meta', handle_get_quiz_meta)
    app.router.add_get('/api/quiz/prewarm', handle_quiz_prewarm)
    app.router.add_post('/api/quiz/complete', handle_quiz_complete)
    app.router.add_post('/api/quiz/answer', handle_quiz_answer)
    app.router.add_get('/api/search/tags', handle_get_search_tags)
    app.router.add_get('/api/profile/taste', handle_get_taste_summary)
    app.router.add_get('/api/tv/progress', handle_get_tv_progress)
    app.router.add_get('/api/tv/season', handle_get_tv_season)
    app.router.add_post('/api/tv/episode-progress', handle_set_tv_episode_progress)
    app.router.add_post('/api/tv/season-progress', handle_set_tv_season_progress)
    app.router.add_post('/api/tv/notifications', handle_set_tv_notifications)
    app.router.add_post('/api/internal/jobs/tv-notifications', handle_tv_notifications_job)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🌐 API сервер запущен на порту {port}")
    return runner

async def main() -> None:
    logger.info("Bot is starting...")
    runner = await start_web_server()
    await bot.delete_webhook(drop_pending_updates=False) 
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Polling error: {e}")
    finally:
        await tmdb.close()
        await bot.session.close()
        await runner.cleanup()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process interrupted")
