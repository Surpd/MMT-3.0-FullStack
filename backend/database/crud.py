import logging
import httpx
from typing import Any, Literal, Optional
from dataclasses import dataclass
from supabase import Client, create_client

logger = logging.getLogger(__name__)

# Типы данных для красоты и подсказок в Cursor
MovieStatus = Literal["liked", "watchlist", "archive", "none"]

@dataclass
class UserMovieRecord:
    user_id: int
    movie_id: int
    media_type: str
    status: MovieStatus
    updated_at: Optional[str]
    rating: Optional[int] = None  # <-- ВОТ ЭТО ОТКАТИЛОСЬ

class DatabaseCRUD:
    def __init__(self, url: str, key: str):
        self._client: Client = create_client(url, key)
        
    async def ensure_user(self, user_id: int) -> None:
        """Регистрация пользователя в таблице profiles."""
        payload = {"id": user_id} 
        # Делаем upsert именно в profiles, чтобы сработал Foreign Key в user_movies
        query = self._client.table("profiles").upsert(payload, on_conflict="id")
        await self._execute(query)

    async def _execute(self, query_builder: Any, max_retries: int = 3) -> Any:
        """Служебный метод для выполнения запросов с защитой от обрывов сети."""
        import asyncio
        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(query_builder.execute)
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Supabase request failed after {max_retries} attempts: {e}")
                    raise e
                await asyncio.sleep(1)

    def _normalize_status(self, status: str) -> MovieStatus:
        """Приводит статус к единому стандарту."""
        s = status.lower()
        if s in ["liked", "watched", "✅ видел"]: return "liked"
        if s in ["watchlist", "⏳ хочу"]: return "watchlist"
        if s in ["archive", "🗑 архив", "disliked"]: return "archive"
        return "none"

    async def upsert_user_movie(self, user_id: int, movie_id: int, status: str, media_type: str = "movie", rating: Optional[int] = None) -> MovieStatus:
        """Обновляет статус фильма у пользователя."""
        normalized_status = self._normalize_status(status)
        
        if normalized_status == "none":
            query = self._client.table("user_movies").delete().eq("user_id", user_id).eq("movie_id", movie_id)
            await self._execute(query)
            return "none"

        payload = {
            "user_id": user_id,
            "movie_id": movie_id,
            "media_type": media_type,
            "status": normalized_status,
            "updated_at": "now()",
        }
        
        # ЕСЛИ ЕСТЬ ОЦЕНКА — СОХРАНЯЕМ
        if rating is not None:
            payload["rating"] = rating
            
        query = self._client.table("user_movies").upsert(payload, on_conflict="user_id,movie_id")
        await self._execute(query)
        return normalized_status

        
    async def get_user_media_by_status(self, user_id: int, status: str) -> list[dict]:
        """Достает список фильмов пользователя по статусу."""
        # ДОБАВЛЕН RATING И GENRES ДЛЯ БИБЛИОТЕКИ И РЕКОМЕНДАЦИЙ
        query = self._client.table("user_movies")\
            .select("movie_id, media_type, rating, movies!inner(title, genres_array)")\
            .eq("user_id", user_id)\
            .eq("status", status)
        
        response = await self._execute(query)
        return response.data if response.data else []

    async def get_user_wish_media_ids(self, user_id: int) -> list[int]:
        """Получает список ID всех фильмов со статусом watchlist для рандома."""
        query = self._client.table("user_movies")\
            .select("movie_id")\
            .eq("user_id", user_id)\
            .eq("status", "watchlist")
            
        response = await self._execute(query)
        return [item["movie_id"] for item in response.data] if response.data else []

    async def get_user_movie(self, user_id: int, movie_id: int) -> Optional[UserMovieRecord]:
        """Достает запись о фильме конкретного юзера."""
        query = self._client.table("user_movies").select("*").eq("user_id", user_id).eq("movie_id", movie_id).limit(1)
        response = await self._execute(query)
        
        if not response.data:
            return None
            
        row = response.data[0]
        return UserMovieRecord(
            user_id=int(row["user_id"]),
            movie_id=int(row["movie_id"]),
            media_type=(row.get("media_type") or "movie"),
            status=row["status"],
            updated_at=row.get("updated_at"),
            rating=row.get("rating")  # <-- ВЫТАСКИВАЕМ ОЦЕНКУ ИЗ БАЗЫ
        )

    async def save_movie(self, movie_data: dict) -> None:
        """Сохраняет расширенные данные фильма в таблицу movies."""
        payload = {
            "id": movie_data.get("id") or movie_data.get("movie_id"),
            "title": movie_data.get("title"),
            "year": str(movie_data.get("year", "    ")),
            "rating_numeric": movie_data.get("rating_numeric") or movie_data.get("tmdb_rating"),
            "overview": movie_data.get("overview"),
            "poster_url": movie_data.get("poster_url"),
            "genres_array": movie_data.get("genres_array") or movie_data.get("genres"),
            "media_type": movie_data.get("media_type", "movie"),
            "actors": movie_data.get("actors") or movie_data.get("cast"),
            "directors": movie_data.get("directors"),
            "runtime_mins": movie_data.get("runtime_mins"),
            "budget": movie_data.get("budget"),
            "revenue": movie_data.get("revenue"),
            # --- ДОБАВЛЕННЫЕ ПОЛЯ ДЛЯ СЕРИАЛОВ ---
            "seasons": movie_data.get("seasons"),
            "tv_status": movie_data.get("tv_status") or movie_data.get("status")
        }
        
        clean_payload = {k: v for k, v in payload.items() if v is not None}
        
        if not clean_payload.get("id"):
            return

        query = self._client.table("movies").upsert(clean_payload, on_conflict="id")
        await self._execute(query)
        
        clean_payload = {k: v for k, v in payload.items() if v is not None}
        
        if not clean_payload.get("id"):
            return

        query = self._client.table("movies").upsert(clean_payload, on_conflict="id")
        await self._execute(query)

    async def get_library_page_rows(self, user_id: int, status: str, start: int, end: int) -> tuple[list[dict], int]:
        """
        Возвращает строки библиотеки пользователя с пагинацией + total count.
        В сервисах должна быть только бизнес-логика (маппинг/форматирование), здесь только запрос к данным.
        """
        query = self._client.table("user_movies") \
            .select("movie_id, media_type, rating, movies(title)", count="exact") \
            .eq("user_id", user_id) \
            .eq("status", status) \
            .order("updated_at", desc=True) \
            .range(start, end)

        response = await self._execute(query)
        rows = response.data if getattr(response, "data", None) else []
        total = response.count if getattr(response, "count", None) is not None else 0
        return rows, total

    async def get_movie(self, movie_id: int) -> dict | None:
        """Проверяет, есть ли фильм в глобальной таблице movies."""
        query = self._client.table("movies").select("id").eq("id", movie_id).limit(1)
        response = await self._execute(query)
        return response.data[0] if response.data else None

    async def get_webapp_library(self, user_id: int, status: str, offset: int, limit: int) -> tuple[list[dict], int]:
        """
        Изолированный метод для Mini App.
        Достает постеры и адаптирован под веб-пагинацию (offset/limit).
        """
        query = self._client.table("user_movies") \
            .select("movie_id, media_type, rating, movies(title, poster_url, seasons, tv_status)", count="exact") \
            .eq("user_id", user_id) \
            .eq("status", status) \
            .order("updated_at", desc=True) \
            .range(offset, offset + limit - 1)

        response = await self._execute(query)
        rows = response.data if getattr(response, "data", None) else []
        total = response.count if getattr(response, "count", None) is not None else 0
        return rows, total