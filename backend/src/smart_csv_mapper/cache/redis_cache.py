"""Redis-backed cache, shared across processes and restarts."""

from redis.asyncio import Redis


class RedisCache:
    name = "redis"

    def __init__(self, client: "Redis") -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str) -> "RedisCache":
        return cls(Redis.from_url(url, decode_responses=True))

    async def get_many(self, keys: list[str]) -> dict[str, str]:
        if not keys:
            return {}
        values = await self._client.mget(keys)
        return {k: str(v) for k, v in zip(keys, values, strict=True) if v is not None}

    async def set_many(self, items: dict[str, str], ttl_seconds: int) -> None:
        async with self._client.pipeline(transaction=False) as pipe:
            for key, value in items.items():
                pipe.set(key, value, ex=ttl_seconds)
            await pipe.execute()
