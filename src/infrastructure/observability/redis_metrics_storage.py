"""
Redis-backed metrics storage for multi-worker deployments.

This module provides distributed metrics storage using Redis, allowing
metrics to be aggregated across multiple Gunicorn workers.

Decision: Redis-backed storage over in-memory:
- Metrics aggregated across all workers (essential for production)
- Survives individual worker restarts
- Consistent view of system metrics
- Minimal performance overhead (Redis is in-memory and fast)
"""

import logging
import time

import redis.asyncio as aioredis
from config.settings import settings

logger = logging.getLogger(__name__)


class RedisMetricsStorage:
    """
    Redis-backed metrics storage for distributed metrics collection.

    Uses Redis data structures:
    - HASH for counters (requests, status codes, business metrics)
    - ZSET for latencies (sorted by timestamp for sliding window)
    """

    def __init__(self, redis_client: aioredis.Redis | None = None):
        """
        Initialize Redis metrics storage.

        Args:
            redis_client: Optional Redis client (injected for testing)
        """
        self._redis: aioredis.Redis | None = redis_client
        self._metrics_ttl = 3600  # Metrics expire after 1 hour of inactivity
        self._latency_window_size = 1000  # Keep last 1000 latency samples per endpoint

    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def increment_request_count(self, endpoint: str) -> None:
        """
        Increment request count for an endpoint.

        Args:
            endpoint: The endpoint (e.g., "GET /api/v1/users")
        """
        try:
            redis = await self._get_redis()
            await redis.hincrby("metrics:request_counts", endpoint, 1)
            await redis.expire("metrics:request_counts", self._metrics_ttl)
        except Exception as e:
            logger.error(f"Failed to increment request count: {e}")

    async def increment_status_count(self, status_code: int) -> None:
        """
        Increment count for a status code.

        Args:
            status_code: HTTP status code
        """
        try:
            redis = await self._get_redis()
            await redis.hincrby("metrics:status_counts", str(status_code), 1)
            await redis.expire("metrics:status_counts", self._metrics_ttl)
        except Exception as e:
            logger.error(f"Failed to increment status count: {e}")

    async def increment_error_count(self) -> None:
        """Increment total error count."""
        try:
            redis = await self._get_redis()
            await redis.incr("metrics:error_count")
            await redis.expire("metrics:error_count", self._metrics_ttl)
        except Exception as e:
            logger.error(f"Failed to increment error count: {e}")

    async def increment_business_metric(self, metric_name: str) -> None:
        """
        Increment a business metric counter.

        Args:
            metric_name: Name of the metric (e.g., "registrations", "activations")
        """
        try:
            redis = await self._get_redis()
            await redis.hincrby("metrics:business", metric_name, 1)
            await redis.expire("metrics:business", self._metrics_ttl)
        except Exception as e:
            logger.error(f"Failed to increment business metric {metric_name}: {e}")

    async def add_latency(self, endpoint: str, duration_ms: float) -> None:
        """
        Add a latency measurement for an endpoint.

        Uses Redis ZSET with timestamp as score to maintain sliding window.

        Args:
            endpoint: The endpoint
            duration_ms: Request duration in milliseconds
        """
        try:
            redis = await self._get_redis()
            key = f"metrics:latencies:{endpoint}"
            current_time = time.time()

            # Add new latency sample with timestamp as score
            member = f"{current_time}:{duration_ms}"
            await redis.zadd(key, {member: current_time})

            # Keep only recent samples (sliding window by count)
            await redis.zremrangebyrank(key, 0, -self._latency_window_size - 1)

            # Set expiry
            await redis.expire(key, self._metrics_ttl)
        except Exception as e:
            logger.error(f"Failed to add latency for {endpoint}: {e}")

    async def get_metrics(self) -> dict:
        """
        Get aggregated metrics from Redis.

        Returns:
            Dictionary containing all metrics
        """
        try:
            redis = await self._get_redis()

            # Get request counts
            request_counts = await redis.hgetall("metrics:request_counts") or {}

            # Get status counts
            status_counts_raw = await redis.hgetall("metrics:status_counts") or {}
            status_counts = {int(k): int(v) for k, v in status_counts_raw.items()}

            # Get error count
            error_count = await redis.get("metrics:error_count")
            error_count = int(error_count) if error_count else 0

            # Get business metrics
            business_metrics_raw = await redis.hgetall("metrics:business") or {}
            business_metrics = {
                "registrations": int(business_metrics_raw.get("registrations", 0)),
                "activations": int(business_metrics_raw.get("activations", 0)),
            }

            # Get latencies and calculate percentiles
            latencies = {}
            latency_keys = await redis.keys("metrics:latencies:*")

            for key in latency_keys:
                endpoint = key.replace("metrics:latencies:", "")

                # Get all latency samples
                samples = await redis.zrange(key, 0, -1)

                if samples:
                    # Extract durations from "timestamp:duration" format
                    durations = []
                    for sample in samples:
                        try:
                            _, duration_str = sample.split(":", 1)
                            durations.append(float(duration_str))
                        except (ValueError, IndexError):
                            continue

                    if durations:
                        sorted_durations = sorted(durations)
                        n = len(sorted_durations)

                        latencies[endpoint] = {
                            "count": n,
                            "p50": self._percentile(sorted_durations, 50),
                            "p95": self._percentile(sorted_durations, 95),
                            "p99": self._percentile(sorted_durations, 99),
                            "min": round(sorted_durations[0], 2),
                            "max": round(sorted_durations[-1], 2),
                        }

            # Convert request counts to dict with int values
            request_counts_dict = {k: int(v) for k, v in request_counts.items()}

            return {
                "request_counts": request_counts_dict,
                "status_counts": status_counts,
                "error_count": error_count,
                "business_metrics": business_metrics,
                "latencies": latencies,
            }

        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {
                "request_counts": {},
                "status_counts": {},
                "error_count": 0,
                "business_metrics": {"registrations": 0, "activations": 0},
                "latencies": {},
            }

    @staticmethod
    def _percentile(sorted_values: list[float], percentile: int) -> float:
        """
        Calculate percentile from sorted values.

        Args:
            sorted_values: List of values sorted in ascending order
            percentile: Percentile to calculate (0-100)

        Returns:
            The value at the specified percentile
        """
        if not sorted_values:
            return 0.0

        k = (len(sorted_values) - 1) * percentile / 100
        f = int(k)
        c = f + 1

        if c >= len(sorted_values):
            return round(sorted_values[-1], 2)

        # Linear interpolation
        d0 = sorted_values[f] * (c - k)
        d1 = sorted_values[c] * (k - f)

        return round(d0 + d1, 2)

    async def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        try:
            redis = await self._get_redis()

            # Delete all metrics keys
            keys_to_delete = []
            keys_to_delete.extend(await redis.keys("metrics:*"))

            if keys_to_delete:
                await redis.delete(*keys_to_delete)

            logger.info("Metrics reset successfully")
        except Exception as e:
            logger.error(f"Failed to reset metrics: {e}")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Global metrics storage instance
_metrics_storage: RedisMetricsStorage | None = None


async def get_metrics_storage() -> RedisMetricsStorage:
    """
    Get or create global metrics storage instance.

    Returns:
        The global RedisMetricsStorage instance
    """
    global _metrics_storage
    if _metrics_storage is None:
        _metrics_storage = RedisMetricsStorage()
    return _metrics_storage
