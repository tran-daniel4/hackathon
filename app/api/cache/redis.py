import os
from redis.asyncio import Redis, ConnectionPool

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            os.environ["REDIS_URL"],
            decode_responses=True,
            max_connections=20,
        )
    return _pool


def get_redis() -> Redis:
    return Redis(connection_pool=get_pool())


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
