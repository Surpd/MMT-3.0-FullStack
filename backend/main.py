import asyncio
import logging
import os
from aiohttp import web
from config import bot, dp, tmdb

# Импортируем наши чистые API обработчики
from web_app.api import (
    handle_get_movies, 
    handle_swipe, 
    handle_get_library, 
    handle_get_movie_details
)

# Роутеры бота (оставляем как было)
from handlers.common import router as common_router
from handlers.library import router as library_router
from handlers.search import router as search_router
from handlers.quiz import router as quiz_router
from handlers.movie import router as movie_router
from handlers.stats import router as stats_router

from middlewares import UserMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("movie_tracker_bot")

dp.message.middleware(UserMiddleware())
dp.callback_query.middleware(UserMiddleware())

dp.include_router(common_router)
dp.include_router(library_router)
dp.include_router(quiz_router)
dp.include_router(movie_router)
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
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
    return response

async def health_check(request):
    return web.Response(text="Bot and API are alive! 🚀")

async def start_web_server():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get('/', health_check)
    
    # === РЕГИСТРАЦИЯ МАРШРУТОВ ИЗ API.PY ===
    app.router.add_get('/api/movies', handle_get_movies)
    app.router.add_post('/api/swipe', handle_swipe)
    app.router.add_get('/api/library', handle_get_library)
    app.router.add_get('/api/movie-details', handle_get_movie_details)
    
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