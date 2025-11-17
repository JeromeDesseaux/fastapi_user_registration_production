"""
Production-grade observability middleware for tracking metrics and performance.

This middleware provides:
1. Request/response metrics (latency, status codes, endpoints)
2. Business metrics (registrations, activations, errors)
3. Structured logging for easy parsing
4. Redis-backed metrics storage (works across multiple workers)

Decision: Redis-backed storage for production multi-worker deployments:
- Metrics aggregated across all Gunicorn workers
- Distributed, consistent view of system metrics
- Survives individual worker restarts
- Can be exported to external monitoring systems (Prometheus, Datadog, etc.)
- Structured logs can be ingested by log aggregators (ELK, Splunk, etc.)
"""

import logging
import time
from collections.abc import Callable

from config.settings import settings
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .redis_metrics_storage import get_metrics_storage

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track HTTP request/response metrics using Redis.

    Tracks:
    - Request latency (p50, p95, p99) - stored in Redis ZSET
    - Status code distribution - stored in Redis HASH
    - Request counts per endpoint - stored in Redis HASH
    - Business metrics (registrations, activations) - stored in Redis HASH

    Metrics are logged as structured JSON and stored in Redis for
    aggregation across multiple Gunicorn workers.
    """

    def __init__(self, app: ASGIApp):
        """
        Initialize metrics middleware.

        Args:
            app: The ASGI application
        """
        super().__init__(app)

    from collections.abc import Awaitable

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process each request and track metrics.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            The HTTP response
        """
        # Skip metrics collection if disabled
        if not settings.enable_metrics:
            return await call_next(request)

        # Start timing
        start_time = time.time()

        # Extract request info
        method = request.method
        path = request.url.path
        endpoint = f"{method} {path}"

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            error = None
        except Exception as e:
            # Log error but re-raise
            status_code = 500
            error = str(e)
            logger.error(
                "Request failed with exception",
                extra={
                    "endpoint": endpoint,
                    "method": method,
                    "path": path,
                    "error": error,
                },
            )
            raise
        finally:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Update metrics in Redis (async, fire-and-forget)
            await self._update_metrics(endpoint, status_code, duration_ms)

            # Log structured metrics
            self._log_request_metrics(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                error=error,
            )

            # Track business metrics
            await self._track_business_metrics(path, status_code)

        return response

    async def _update_metrics(
        self,
        endpoint: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Update metrics in Redis storage."""
        try:
            storage = await get_metrics_storage()

            # Add latency sample
            await storage.add_latency(endpoint, duration_ms)

            # Increment request count
            await storage.increment_request_count(endpoint)

            # Increment status count
            await storage.increment_status_count(status_code)

            # Increment error count if applicable
            if status_code >= 400:
                await storage.increment_error_count()
        except Exception as e:
            # Don't fail requests if metrics storage fails
            logger.error(f"Failed to update metrics: {e}")

    def _log_request_metrics(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        error: str | None = None,
    ) -> None:
        """Log request metrics as structured JSON."""
        log_data = {
            "type": "request_metric",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        }

        if error:
            log_data["error"] = error

        # Use appropriate log level based on status
        if status_code >= 500:
            logger.error("Request completed with server error", extra=log_data)
        elif status_code >= 400:
            logger.warning("Request completed with client error", extra=log_data)
        else:
            logger.info("Request completed successfully", extra=log_data)

    async def _track_business_metrics(self, path: str, status_code: int) -> None:
        """Track business-specific metrics in Redis."""
        # Only count successful requests
        if status_code < 400:
            try:
                storage = await get_metrics_storage()

                if "/register" in path:
                    await storage.increment_business_metric("registrations")
                    logger.info(
                        "User registration",
                        extra={
                            "type": "business_metric",
                            "metric": "registration",
                        },
                    )
                elif "/activate" in path:
                    await storage.increment_business_metric("activations")
                    logger.info(
                        "User activation",
                        extra={
                            "type": "business_metric",
                            "metric": "activation",
                        },
                    )
            except Exception as e:
                logger.error(f"Failed to track business metrics: {e}")

    async def get_metrics(self) -> dict:
        """
        Get current metrics snapshot from Redis.

        Returns:
            Dictionary containing all tracked metrics aggregated across workers
        """
        try:
            storage = await get_metrics_storage()
            return await storage.get_metrics()
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {
                "request_counts": {},
                "status_counts": {},
                "error_count": 0,
                "business_metrics": {"registrations": 0, "activations": 0},
                "latencies": {},
            }

    async def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        try:
            storage = await get_metrics_storage()
            await storage.reset_metrics()
        except Exception as e:
            logger.error(f"Failed to reset metrics: {e}")
