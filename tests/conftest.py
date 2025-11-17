"""
Pytest configuration and shared fixtures.

This file provides common fixtures and configuration for all tests.

Decision: Removed custom event_loop fixture in favor of pytest-asyncio's
built-in handling with asyncio_mode = "auto" configured in pyproject.toml.
"""

import os

# Set test environment variables
# Use .setdefault() to respect values already set by docker-compose or other sources
os.environ.setdefault("DATABASE_HOST", "localhost")
os.environ.setdefault("DATABASE_PORT", "5432")
os.environ.setdefault("DATABASE_NAME", "test_user_registration")
os.environ.setdefault("DATABASE_USER", "postgres")
os.environ.setdefault("DATABASE_PASSWORD", "postgres")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("LOG_LEVEL", "ERROR")

# Disable middleware features for tests by default
# Individual tests can override by setting these to "true" before importing the app
os.environ.setdefault("ENABLE_METRICS", "false")
os.environ.setdefault("ENABLE_RATE_LIMITING", "false")
