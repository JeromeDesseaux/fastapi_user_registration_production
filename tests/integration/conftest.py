"""
pytest fixtures for integration tests.

Integration tests use:
- FastAPI's TestClient (in-process, no Docker needed)
- Dependency overrides to inject MockTaskQueue instead of real Celery
- Real database connection
- Automatic cleanup between tests

Decision: Using TestClient instead of httpx to Docker API is faster
and more appropriate for integration tests. We save Docker/Behave for E2E.
"""

import os

import asyncpg
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.presentation.dependencies import get_task_queue
from tests.mocks.mock_task_queue import MockTaskQueue

# Database configuration for test cleanup
DB_CONFIG = {
    "host": os.getenv("DATABASE_HOST", "localhost"),
    "port": int(os.getenv("DATABASE_PORT", "5432")),
    "database": os.getenv("DATABASE_NAME", "user_registration"),
    "user": os.getenv("DATABASE_USER", "postgres"),
    "password": os.getenv("DATABASE_PASSWORD", "postgres"),
}


@pytest.fixture(autouse=True)
async def clean_database_before_test():
    """
    Clean database before each test.

    This ensures test isolation - each test starts with a clean slate.

    Decision: autouse=True means this runs automatically for every test.
    """
    # Clean database
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
    except Exception as e:
        print(f"Warning: Could not clean database: {e}")

    yield


@pytest.fixture
def api_client():
    """
    Create FastAPI TestClient with MockTaskQueue dependency override.

    Returns:
        TestClient instance for making API requests

    Decision: Using TestClient as a context manager ensures the app's
    lifespan events (startup/shutdown) are triggered, which initializes
    the database connection pool.

    We use dependency_overrides to inject MockTaskQueue instead of
    CeleryTaskQueue, which is cleaner than environment variable checks.
    """
    # Clear mock task queue before each test
    MockTaskQueue.clear()

    # Override the task queue dependency with MockTaskQueue
    app.dependency_overrides[get_task_queue] = lambda: MockTaskQueue()

    with TestClient(app) as client:
        yield client

    # Clean up overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
async def db_connection():
    """
    Provide direct database connection for assertions.

    Useful when tests need to verify database state directly.

    Yields:
        asyncpg Connection object

    Example:
        async def test_something(db_connection):
            user = await db_connection.fetchrow(
                "SELECT * FROM users WHERE email = $1",
                "test@example.com"
            )
            assert user is not None
    """
    conn = await asyncpg.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
    yield conn
    await conn.close()


@pytest.fixture
def register_user(api_client):
    """
    Helper fixture to register a user.

    Returns a function that registers a user and returns the response.

    Usage:
        def test_something(register_user):
            response = register_user("test@example.com", "SecurePass123")
            assert response.status_code == 201

    Decision: This reduces boilerplate in tests that need a registered user.
    """

    def _register(email: str, password: str):
        return api_client.post(
            "/api/v1/users/register", json={"email": email, "password": password}
        )

    return _register


@pytest.fixture
def get_mock_tasks():
    """
    Helper fixture to get tasks from MockTaskQueue directly.

    Returns a function that fetches mock tasks.

    Usage:
        def test_something(api_client, get_mock_tasks):
            api_client.post("/api/v1/users/register", json={...})
            tasks = get_mock_tasks()
            assert len(tasks) == 1

    Decision: Accesses MockTaskQueue directly instead of via HTTP endpoint,
    which is cleaner and faster.
    """

    def _get_tasks():
        return MockTaskQueue.get_all_tasks()

    return _get_tasks


@pytest.fixture
def get_activation_code_from_queue(get_mock_tasks):
    """
    Helper to extract activation code for a user from mock task queue.

    Returns a function that gets the code for a specific email.

    Usage:
        def test_activation(register_user, get_activation_code_from_queue):
            register_user("test@example.com", "Pass123")
            code = get_activation_code_from_queue("test@example.com")
            # Use code for activation...

    Decision: Common pattern in tests - simplifies activation test setup.
    """

    def _get_code(email: str):
        tasks = get_mock_tasks()
        matching_tasks = [t for t in tasks if t["email"] == email]
        assert len(matching_tasks) > 0, f"No task found for {email}. Available: {tasks}"
        return matching_tasks[0]["code"]

    return _get_code
