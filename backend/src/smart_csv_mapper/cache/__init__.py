"""Key-value cache for AI transform results (ADR-007): in memory by default, Redis if configured."""

import time
from collections.abc import Callable
from typing import Protocol

DEFAULT_TTL_SECONDS = 30 * 24 * 3600


class Cache(Protocol):
    name: str

    async def get_many(self, keys: list[str]) -> dict[str, str]: ...

    async def set_many(self, items: dict[str, str], ttl_seconds: int) -> None: ...


class InMemoryCache:
    name = "memory"

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._items: dict[str, tuple[str, float]] = {}

    async def get_many(self, keys: list[str]) -> dict[str, str]:
        now = self._clock()
        found = {}
        for key in keys:
            item = self._items.get(key)
            if item is not None and item[1] > now:
                found[key] = item[0]
        return found

    async def set_many(self, items: dict[str, str], ttl_seconds: int) -> None:
        expires = self._clock() + ttl_seconds
        for key, value in items.items():
            self._items[key] = (value, expires)
