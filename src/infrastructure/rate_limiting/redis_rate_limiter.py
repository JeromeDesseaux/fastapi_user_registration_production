"""
Redis-based sliding window rate limiter.

This module implements a production-grade rate limiter using Redis ZSET
for accurate sliding window rate limiting.

Decision: Redis sliding window over in-memory fixed window:
- More accurate at window boundaries (no burst at window reset)
- Distributed - works across multiple API instances
- Redis already in stack (used by Celery)
- Industry standard approach (Cloudflare, AWS API Gateway use similar)

Algorithm:
1. Use Redis ZSET with scores as timestamps
2. Remove entries outside the current window
3. Count remaining entries
4. If under limit, add new entry and allow request
5. If over limit, reject with retry-after header
"""

import logging
import time

import redis.asyncio as aioredis
from config.settings import settings

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """
    Sliding window rate limiter using Redis ZSET.

    Each rate limit window is stored as a Redis sorted set (ZSET)
    where members are request IDs and scores are timestamps.
    """

    def __init__(self, redis_client: aioredis.Redis | None = None):
        """
        Initialize rate limiter.

        Args:
            redis_client: Optional Redis client (injected for testing)
        """
        self._redis: aioredis.Redis | None = redis_client

    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window_seconds: int,
        rate_limit_type: str = "general",
    ) -> tuple[bool, dict[str, int]]:
        """
        Check if request should be rate limited.

        Args:
            identifier: Unique identifier for rate limit (e.g., IP address, user email)
            limit: Maximum number of requests allowed in the window
            window_seconds: Time window in seconds
            rate_limit_type: Type of rate limit (for Redis key namespacing)

        Returns:
            Tuple of (allowed: bool, headers: dict)
            - allowed: True if request is within rate limit
            - headers: Dict with X-RateLimit-* header values
        """
        # Skip if rate limiting is disabled
        if not settings.enable_rate_limiting:
            return True, {}

        redis = await self._get_redis()
        current_time = time.time()
        window_start = current_time - window_seconds

        # Redis key for this rate limit
        key = f"ratelimit:{rate_limit_type}:{identifier}"

        try:
            # Use Redis pipeline for atomic operations
            pipe = redis.pipeline()

            # 1. Remove entries outside the current window
            pipe.zremrangebyscore(key, "-inf", window_start)

            # 2. Count entries in current window
            pipe.zcard(key)

            # 3. Add current request timestamp (with unique member)
            request_id = f"{current_time}:{id(object())}"
            pipe.zadd(key, {request_id: current_time})

            # 4. Set expiry on the key (cleanup old keys)
            pipe.expire(key, window_seconds * 2)

            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]  # Result of zcard

            # Calculate rate limit info
            allowed = current_count < limit
            remaining = max(0, limit - current_count - 1)

            if not allowed:
                # Request would exceed limit, remove the entry we just added
                await redis.zrem(key, request_id)

                # Calculate retry-after (time until oldest entry expires)
                oldest_entries = await redis.zrange(key, 0, 0, withscores=True)
                if oldest_entries:
                    oldest_timestamp = oldest_entries[0][1]
                    retry_after = int(oldest_timestamp + window_seconds - current_time) + 1
                else:
                    retry_after = window_seconds

                headers = {
                    "X-RateLimit-Limit": limit,
                    "X-RateLimit-Remaining": 0,
                    "X-RateLimit-Reset": int(current_time + retry_after),
                    "Retry-After": retry_after,
                }

                logger.warning(
                    f"Rate limit exceeded for {identifier}",
                    extra={
                        "type": "rate_limit",
                        "identifier": identifier,
                        "limit": limit,
                        "window_seconds": window_seconds,
                        "current_count": current_count,
                        "retry_after": retry_after,
                    },
                )

                return False, headers

            # Request allowed
            headers = {
                "X-RateLimit-Limit": limit,
                "X-RateLimit-Remaining": remaining,
                "X-RateLimit-Reset": int(current_time + window_seconds),
            }

            return True, headers

        except Exception as e:
            # On Redis errors, fail open (allow request) to avoid service disruption
            logger.error(
                f"Rate limiter error, failing open: {e}",
                extra={
                    "type": "rate_limit_error",
                    "identifier": identifier,
                    "error": str(e),
                },
            )
            return True, {}

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Global rate limiter instance
_rate_limiter: RedisRateLimiter | None = None


async def get_rate_limiter() -> RedisRateLimiter:
    """
    Get or create global rate limiter instance.

    Returns:
        The global RedisRateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RedisRateLimiter()
    return _rate_limiter
