import asyncio
from typing import Any

class MemoryCache:
    def __init__(self, ttl_sec: int):
        self._ttl_sec = ttl_sec
        self._store: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        """Достает данные, если они еще не протухли."""
        now = asyncio.get_running_loop().time()
        cached = self._store.get(key)
        
        if not cached:
            return None
            
        expires_at, value = cached
        if now > expires_at:
            self._store.pop(key, None)
            return None
            
        return value

    async def put(self, key: str, value: Any, ttl_sec: int | None = None) -> None:
        """Кладет данные с учетом времени жизни (TTL)."""
        now = asyncio.get_running_loop().time()
        for stale_key, (expires_at, _) in list(self._store.items()):
            if now > expires_at:
                self._store.pop(stale_key, None)
        self._store[key] = (now + (ttl_sec if ttl_sec is not None else self._ttl_sec), value)
    
    async def delete(self, key: str) -> None:
        """Принудительно удаляет данные (нужно для сброса очереди)."""
        self._store.pop(key, None)

    async def delete_prefix(self, prefix: str) -> None:
        """Удаляет связанные ключи без раскрытия внутреннего store callers."""
        for key in [key for key in self._store if key.startswith(prefix)]:
            self._store.pop(key, None)
