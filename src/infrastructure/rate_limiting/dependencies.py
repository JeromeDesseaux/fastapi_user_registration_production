"""
FastAPI dependencies for endpoint-specific rate limiting.

Provides rate limit checks that can be injected into route handlers.
"""

import logging

from config.settings import settings
from fastapi import HTTPException, Request, status

from .redis_rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


async def check_registration_rate_limit(request: Request) -> None:
    """
    Rate limit dependency for user registration endpoint.

    Limits registration requests to 5 per hour per IP address.

    Args:
        request: The FastAPI request object

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    # Skip if rate limiting is disabled
    if not settings.enable_rate_limiting:
        return

    # Get client IP address
    client_ip = request.client.host if request.client else "unknown"

    # Get rate limiter
    rate_limiter = await get_rate_limiter()

    # Check rate limit
    allowed, headers = await rate_limiter.check_rate_limit(
        identifier=client_ip,
        limit=settings.rate_limit_registration_per_hour,
        window_seconds=3600,  # 1 hour
        rate_limit_type="registration",
    )

    if not allowed:
        logger.warning(
            f"Registration rate limit exceeded for IP: {client_ip}",
            extra={
                "type": "rate_limit_exceeded",
                "endpoint": "registration",
                "ip": client_ip,
                "limit": settings.rate_limit_registration_per_hour,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RateLimitExceeded",
                "message": f"Too many registration attempts. You can register up to {settings.rate_limit_registration_per_hour} accounts per hour.",
                "retry_after_seconds": headers.get("Retry-After", 3600),
            },
            headers={k: str(v) for k, v in headers.items()},
        )


async def check_activation_rate_limit(request: Request, email: str) -> None:
    """
    Rate limit dependency for account activation endpoint.

    Limits activation attempts to 3 per minute per email address.

    Args:
        request: The FastAPI request object
        email: The user's email address (from Basic Auth)

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    # Skip if rate limiting is disabled
    if not settings.enable_rate_limiting:
        return

    # Get rate limiter
    rate_limiter = await get_rate_limiter()

    # Check rate limit (per email address)
    allowed, headers = await rate_limiter.check_rate_limit(
        identifier=email,
        limit=settings.rate_limit_activation_per_minute,
        window_seconds=60,  # 1 minute
        rate_limit_type="activation",
    )

    if not allowed:
        logger.warning(
            f"Activation rate limit exceeded for email: {email}",
            extra={
                "type": "rate_limit_exceeded",
                "endpoint": "activation",
                "email": email,
                "limit": settings.rate_limit_activation_per_minute,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RateLimitExceeded",
                "message": f"Too many activation attempts. You can try up to {settings.rate_limit_activation_per_minute} times per minute.",
                "retry_after_seconds": headers.get("Retry-After", 60),
            },
            headers={k: str(v) for k, v in headers.items()},
        )
