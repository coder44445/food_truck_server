import redis.asyncio as redis
from typing import Optional
from core.config import settings

# Global variable to hold the ASYNCHRONOUS Redis connection pool
redis_pool: Optional[redis.ConnectionPool] = None
redis_client: Optional[redis.Redis] = None

async def init_redis_pool():
    global redis_pool, redis_client
    try:
        redis_pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        redis_client = redis.Redis(connection_pool=redis_pool)
        await redis_client.ping()
        print("Redis connection pool initialized successfully (Asynchronous).",settings.REDIS_HOST,settings.REDIS_PORT)
    except Exception as e:
        print(f"Could not connect to Redis: {e}")

async def close_redis_pool():
    """Closes the Redis connection pool (for application shutdown)."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None

def get_redis_client() -> redis.Redis:
    """Dependency injection function to get the asynchronous Redis client."""
    if redis_client is None:
        raise ConnectionError("Redis client is not initialized.")
    return redis_client
