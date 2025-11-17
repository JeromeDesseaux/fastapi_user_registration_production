"""
Main application entry point.

This module initializes and configures the FastAPI application.
It handles startup/shutdown events and wires everything together.
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from config.settings import settings
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.infrastructure.observability.metrics_middleware import MetricsMiddleware
from src.infrastructure.rate_limiting.middleware import GlobalRateLimitMiddleware
from src.presentation.dependencies import get_database_connection
from src.presentation.routes import router

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events:
    - Startup: Initialize database connection and schema
    - Shutdown: Close database connections gracefully

    Decision: Using the new lifespan context manager (FastAPI 0.93+)
    instead of deprecated @app.on_event decorators.
    """
    # Startup
    logger.info("Starting User Registration API...")

    # Initialize database connection
    db = get_database_connection()
    await db.connect()
    logger.info("Database connection pool initialized")

    # Initialize database schema
    await db.init_schema()
    logger.info("Database schema initialized")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down User Registration API...")
    await db.disconnect()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="User Registration API",
    description="""
    User registration and activation API for Dailymotion.

    ## Features
    - User registration with email/password
    - Email verification with 4-digit code
    - Account activation with Basic Auth
    - Asynchronous email sending via Celery
    - Clean Architecture / Hexagonal Architecture

    ## Technical Stack
    - FastAPI for REST API
    - PostgreSQL for persistence
    - Celery + Redis for async tasks
    - Docker for containerization
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
# Decision: Allow all origins for development/demo.
# In production, restrict to specific domains.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add observability middleware (conditionally)
# Decision: Metrics can be disabled via environment variable for testing
metrics_middleware: MetricsMiddleware | None = None
if settings.enable_metrics:
    # Middleware uses shared class-level storage for metrics
    app.add_middleware(MetricsMiddleware)
    metrics_middleware = MetricsMiddleware(app)  # Instance for /metrics endpoint
    logger.info("Metrics middleware enabled")
else:
    metrics_middleware = None
    logger.info("Metrics middleware disabled")

# Add rate limiting middleware (conditionally)
# Decision: Rate limiting can be disabled via environment variable for testing
if settings.enable_rate_limiting:
    app.add_middleware(GlobalRateLimitMiddleware)
    logger.info("Rate limiting middleware enabled")
else:
    logger.info("Rate limiting middleware disabled")


# Custom exception handler for Pydantic validation errors
# Decision: Return 400 Bad Request instead of 422 Unprocessable Entity
# This is more semantically correct and provides consistent error format
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors and return 400 Bad Request.

    Decision: We use 400 instead of FastAPI's default 422 because:
    - 400 is more semantically correct for client input validation
    - Provides consistent error format across all endpoints
    - Matches REST API conventions
    """
    errors = exc.errors()
    error_messages = [f"{err['loc'][-1]}: {err['msg']}" for err in errors]

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": {
                "error": "ValidationError",
                "message": "Request validation failed",
                "errors": error_messages,
            }
        },
    )


# Include routes
app.include_router(router)


# Root endpoint
@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "service": "User Registration API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health",
        "metrics": "/api/v1/metrics",
    }


# Health check endpoint
@app.get("/api/v1/health", tags=["monitoring"])
async def health_check() -> dict[str, str | dict]:
    """
    Health check endpoint.

    Returns the API health status and database connectivity.
    """
    db_status = "unknown"

    try:
        # Check database connectivity
        db = get_database_connection()
        db_status = "healthy" if getattr(db, "pool", getattr(db, "_pool", None)) else "unhealthy"
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db_status = "unhealthy"

    overall_status = "healthy" if db_status == "healthy" else "degraded"

    return {
        "status": overall_status,
        "version": "1.0.0",
        "checks": {
            "database": db_status,
        },
    }


# Metrics endpoint
@app.get("/api/v1/metrics", tags=["monitoring"])
async def get_metrics_endpoint() -> dict:
    """
    Metrics endpoint.

    Returns current metrics aggregated across all workers if metrics middleware is enabled.
    """
    if not settings.enable_metrics or metrics_middleware is None:
        return {
            "error": "MetricsDisabled",
            "message": "Metrics collection is disabled. Enable with ENABLE_METRICS=true",
        }

    # Get metrics from Redis (aggregated across all workers)
    return await metrics_middleware.get_metrics()


if __name__ == "__main__":
    import uvicorn

    # Run with uvicorn for both dev & production
    # This way we reflect the production env on dev
    # machines avoiding the good old classic : "I don't get
    # this bug, it works on my machine". You know what I mean.
    uvicorn.run(
        "src.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("API_RELOAD", "False").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
