"""
Behave environment configuration for E2E tests.

E2E tests use:
- Real Docker services (API, Celery, Redis, Mailhog, PostgreSQL)
- Real Celery workers sending actual emails
- Mailhog API for email verification
- Real HTTP requests to API container

Decision: E2E tests verify the complete workflow end-to-end.
This is slower but provides comprehensive validation.
"""

import asyncio
import os
import time

import asyncpg
import httpx
from tests.e2e.helpers.mailhog_client import MailhogClient

# Disable middleware features for E2E tests by default
# This ensures consistent test behavior and avoids rate limiting during tests
os.environ.setdefault("ENABLE_METRICS", "false")
os.environ.setdefault("ENABLE_RATE_LIMITING", "false")

# API base URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Mailhog URL
MAILHOG_URL = os.getenv("MAILHOG_URL", "http://mailhog:8025")

# Database configuration for test cleanup
DB_CONFIG = {
    "host": os.getenv("DATABASE_HOST", "postgres"),
    "port": int(os.getenv("DATABASE_PORT", "5432")),
    "database": os.getenv("DATABASE_NAME", "user_registration"),
    "user": os.getenv("DATABASE_USER", "postgres"),
    "password": os.getenv("DATABASE_PASSWORD", "postgres"),
}


async def clean_test_database_async():
    """
    Clean the test database by truncating the users table.

    Decision: E2E tests also need clean database between scenarios.
    """
    try:
        conn = await asyncpg.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
        )
        await conn.execute("TRUNCATE TABLE users CASCADE;")
        await conn.close()
        print("✓ Test database cleaned")
    except Exception as e:
        print(f"Warning: Could not clean database: {e}")


def clean_test_database():
    """Synchronous wrapper for async cleanup."""
    asyncio.run(clean_test_database_async())


def before_all(context):
    """
    Set up before all E2E tests.

    Decision: We wait for all services (API, Celery, Mailhog) to be ready
    before running E2E tests. This is critical in Docker environments.
    """
    context.api_base_url = API_BASE_URL
    context.client = httpx.Client(base_url=API_BASE_URL, timeout=30.0)
    context.mailhog = MailhogClient(base_url=MAILHOG_URL)

    # Wait for API to be ready
    max_retries = 30
    for i in range(max_retries):
        try:
            response = context.client.get("/api/v1/health")
            if response.status_code == 200:
                print(f"\n✓ API is ready at {API_BASE_URL}")
                break
        except Exception:
            if i == max_retries - 1:
                raise Exception(f"API not ready after {max_retries} retries") from None
            time.sleep(1)

    # Wait for Mailhog to be ready
    max_retries = 10
    for i in range(max_retries):
        try:
            context.mailhog.get_all_messages()
            print("✓ Mailhog is ready")
            break
        except Exception:
            if i == max_retries - 1:
                print("Warning: Mailhog not ready, email verification may fail")
            time.sleep(1)

    # Clean database before running tests
    clean_test_database()

    # Clear Mailhog emails
    try:
        context.mailhog.clear_all_messages()
        print("✓ Mailhog emails cleared")
    except Exception as e:
        print(f"Warning: Could not clear Mailhog: {e}")


def after_all(context):
    """Clean up after all E2E tests."""
    context.client.close()
    context.mailhog.close()


def before_scenario(context, scenario):
    """
    Set up before each E2E scenario.

    Ensures complete isolation between scenarios by:
    - Cleaning database
    - Clearing Mailhog emails
    - Resetting context variables

    Decision: E2E tests must be completely independent.
    """
    context.response = None
    context.user_email = None
    context.user_password = None
    context.activation_code = None
    context.activation_code_from_email = None

    # Clean database before each scenario
    clean_test_database()

    # Clear Mailhog emails before each scenario
    try:
        context.mailhog.clear_all_messages()
        print("✓ Mailhog emails cleared for scenario")
    except Exception as e:
        print(f"Warning: Could not clear Mailhog: {e}")


def after_scenario(context, scenario):
    """Clean up after each E2E scenario."""
    pass
