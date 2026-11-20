import fakeredis
import pytest

from smart_csv_mapper.cache import InMemoryCache
from smart_csv_mapper.cache.redis_cache import RedisCache
from smart_csv_mapper.config import Settings
from smart_csv_mapper.main import build_cache


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


async def test_memory_cache_returns_only_the_keys_it_has() -> None:
    cache = InMemoryCache()
    await cache.set_many({"a": "1", "b": "2"}, ttl_seconds=60)
    assert await cache.get_many(["a", "b", "c"]) == {"a": "1", "b": "2"}


async def test_memory_cache_expires_items_after_the_ttl() -> None:
    clock = Clock()
    cache = InMemoryCache(clock)
    await cache.set_many({"a": "1"}, ttl_seconds=10)
    clock.now = 9.9
    assert await cache.get_many(["a"]) == {"a": "1"}
    clock.now = 10
    assert await cache.get_many(["a"]) == {}


@pytest.fixture
def redis_cache() -> RedisCache:
    return RedisCache(fakeredis.FakeAsyncRedis(decode_responses=True))


async def test_redis_cache_round_trip_with_ttl(redis_cache: RedisCache) -> None:
    await redis_cache.set_many({"k1": "v1", "k2": "v2"}, ttl_seconds=60)
    assert await redis_cache.get_many(["k1", "k2", "k3"]) == {"k1": "v1", "k2": "v2"}
    assert 0 < await redis_cache._client.ttl("k1") <= 60


async def test_redis_cache_with_no_keys_does_not_call_redis(redis_cache: RedisCache) -> None:
    await redis_cache._client.aclose()
    assert await redis_cache.get_many([]) == {}


def test_build_cache_uses_redis_only_when_a_url_is_set() -> None:
    assert isinstance(build_cache(Settings()), InMemoryCache)
    redis = build_cache(Settings(redis_url="redis://localhost:6379/0"))
    assert isinstance(redis, RedisCache)
