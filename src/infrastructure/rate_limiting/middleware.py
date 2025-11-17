"""
Global rate limiting middleware.

Applies rate limits to all endpoints to protect against DDoS and abuse.
"""

import logging
from collections.abc import Callable

from config.settings import settings
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from .redis_rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to apply global rate limiting to all endpoints.

    Limits the number of requests per minute per endpoint to prevent abuse.
    """

    def __init__(self, app: ASGIApp):
        """
        Initialize global rate limit middleware.

        Args:
            app: The ASGI application
        """
        super().__init__(app)

    from collections.abc import Awaitable

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process each request and check global rate limit.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            The HTTP response or 429 if rate limited
        """
        # Skip if rate limiting is disabled
        if not settings.enable_rate_limiting:
            return await call_next(request)

        # Extract endpoint info
        method = request.method
        path = request.url.path
        endpoint = f"{method}:{path}"

        # Get rate limiter
        rate_limiter = await get_rate_limiter()

        # Check global rate limit (per endpoint)
        allowed, headers = await rate_limiter.check_rate_limit(
            identifier=endpoint,
            limit=settings.rate_limit_global_per_minute,
            window_seconds=60,
            rate_limit_type="global",
        )

        if not allowed:
            # Rate limit exceeded
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RateLimitExceeded",
                    "message": f"Too many requests to {endpoint}. Please try again later.",
                    "retry_after_seconds": headers.get("Retry-After", 60),
                },
                headers={k: str(v) for k, v in headers.items()},
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response.headers[header_name] = str(header_value)

        return response
