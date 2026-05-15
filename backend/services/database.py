from __future__ import annotations
import httpx
import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from supabase import Client, create_client
from database.crud import DatabaseCRUD, UserMovieRecord

logger = logging.getLogger(__name__)

@dataclass(slots=True)
class UserMedia:
    status: str
    rating: int | None
    media_type: str = "movie"
    updated_at: str | None = None
    
class SupabaseDatabase:
    def __init__(self, url: str, key: str) -> None:
        self._client: Client = create_client(url, key)
        # Инициализируем наш CRUD слой
        self._crud = DatabaseCRUD(url=url, key=key)

    @staticmethod
    async def _execute(query_builder: Any, max_retries: int = 3) -> Any:
        """Служебный метод для выполнения запросов с защитой от любых сбоев сети."""
        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(query_builder.execute)
            # Заменили ConnectError на RequestError (ловит ВСЕ сетевые проблемы)
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(1) # Ждем секунду и пробуем снова по новому каналу

    async def ensure_user(self, user_id: int, username: str = None, first_name: str = None):
        """Регистрация пользователя и его кошелька статистики."""
        # 1. Создаем/обновляем данные профиля
        # Сначала готовим запрос (БЕЗ .execute() в конце!)
        query_user = self._client.table("users").upsert({
            "id": user_id, 
            "username": username, 
            "first_name": first_name
        })
        # А теперь выполняем его через твой асинхронный хелпер
        await self._execute(query_user)

        # 2. Создаем запись в статистике
        query_stats = self._client.table("user_stats").upsert(
            {"user_id": user_id}, 
            on_conflict="user_id"
        )
        await self._execute(query_stats) # И тут тоже через хелпер


    async def get_user_stats(self, user_id: int):
        """Забирает всю строку со статистикой юзера."""
        # 1. Готовим запрос, НО НЕ вызываем .execute() в конце!
        query = self._client.table("user_stats").select("*").eq("user_id", user_id).single()
        
        # 2. Передаем этот запрос в наш внутренний хелпер[cite: 2]
        res = await self._execute(query)
        return res.data

    async def update_user_stats(self, user_id: int, stats_data: dict):
        """Сохраняет обновленные цифры статистики."""
        # Готовим запрос на обновление[cite: 2]
        query = self._client.table("user_stats").update(stats_data).eq("user_id", user_id)
        
        # Выполняем через хелпер[cite: 2]
        return await self._execute(query)

    async def get_movie(self, movie_id: int) -> dict | None:
        """Получение данных фильма в виде словаря."""
        query = self._client.table("movies").select("*").eq("id", movie_id).limit(1)
        response = await self._execute(query)
        return response.data[0] if response.data else None

    async def save_movie(self, movie_data: dict) -> None:
        """Сохранение данных фильма через CRUD."""
        await self._crud.save_movie(movie_data)

    async def upsert_user_movie(
        self, 
        user_id: int, 
        movie_id: int, 
        status: str, 
        media_type: str = "movie", 
        rating: int | None = None
    ):
        """Прослойка, которая передает всё в CRUD (с поддержкой рейтинга и типа медиа)."""
        return await self._crud.upsert_user_movie(
            user_id=user_id, 
            movie_id=movie_id, 
            status=status, 
            media_type=media_type, 
            rating=rating
        )

    async def get_user_movie(self, user_id: int, movie_id: int) -> UserMedia | None:
        """Получение статуса и рейтинга конкретного фильма для юзера."""
        record: UserMovieRecord | None = await self._crud.get_user_movie(user_id=user_id, movie_id=movie_id)
        if record is None:
            return None
        return UserMedia(
            status=record.status,
            rating=record.rating, 
            media_type=getattr(record, 'media_type', 'movie'), # <--- ДОБАВИЛИ ВОТ ЭТУ СТРОКУ
            updated_at=record.updated_at,
        )

    async def get_user_wish_media_ids(self, user_id: int) -> list[int]:
        """Для функции 'Что посмотреть'."""
        return await self._crud.get_user_wish_media_ids(user_id=user_id)

    async def get_user_media_by_status(self, user_id: int, status: str) -> list[Any]:
        """Для отображения списков в библиотеке."""
        return await self._crud.get_user_media_by_status(user_id=user_id, status=status)
        
    async def get_library_page_rows(self, user_id: int, status: str, start: int, end: int):
        """
        Запрос к Supabase для получения списка фильмов с пагинацией.
        """
        query = self._client.table("user_movies") \
            .select("movie_id, media_type, rating, movies(title)", count="exact") \
            .eq("user_id", user_id) \
            .eq("status", status) \
            .order("updated_at", desc=True) \
            .range(start, end)

        # Выполняем запрос через твой внутренний метод или напрямую
        response = await self._execute(query) 
        
        rows = response.data if hasattr(response, "data") else []
        total = response.count if hasattr(response, "count") else 0
        
        return rows, total

    async def get_webapp_library(self, user_id: int, status: str, offset: int, limit: int) -> tuple[list[dict], int]:
        """
        Специальный метод для Mini App: достает фильмы с пагинацией (offset, limit)
        и возвращает сами записи + их общее количество.
        """
        try:
            # 1. Сначала узнаем ОБЩЕЕ количество фильмов с таким статусом
            count_response = await self._execute(
                self._client.table("user_movies")
                .select("*", count="exact")
                .eq("user_id", user_id)
                .eq("status", status)
            )
            total = count_response.count if count_response.count else 0

            # 2. Теперь запрашиваем конкретную страницу (с offset до offset+limit-1)
            # Заодно джоиним таблицу movies, чтобы сразу получить названия и постеры
            data_response = await self._execute(
                self._client.table("user_movies")
                .select("movie_id, rating, media_type, movies(*)")
                .eq("user_id", user_id)
                .eq("status", status)
                .range(offset, offset + limit - 1)
                .order("created_at", desc=True) # Сортируем: новые сверху
            )
            
            rows = data_response.data if data_response.data else []
            return rows, total
            
        except Exception as e:
            self.logger.error(f"Ошибка в get_webapp_library: {e}")
            return [], 0