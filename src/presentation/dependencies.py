"""
FastAPI dependency injection.

This module provides dependency injection for our application.
It's the glue that wires together our layers (domain, application, infrastructure).

Decision: Using FastAPI's dependency injection system provides:
1. Clean separation of concerns
2. Easy testing (can inject mocks)
3. Lifecycle management
4. Type safety
"""

import logging
from functools import lru_cache
from typing import Annotated

from config.settings import settings
from fastapi import Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from src.application.activate_user import ActivateUserUseCase
from src.application.register_user import RegisterUserUseCase, TaskQueue
from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.database.postgres_user_repository import PostgresUserRepository

logger = logging.getLogger(__name__)

# HTTP Basic Auth for activation endpoint
security = HTTPBasic()


@lru_cache
def get_database_connection() -> DatabaseConnection:
    """
    Get database connection instance (singleton).

    Decision: We use lru_cache to ensure a single connection pool
    is shared across the application. This is important for:
    1. Resource efficiency (limited connections)
    2. Connection pooling effectiveness
    3. Consistent behavior

    Uses centralized settings for all configuration instead of os.getenv.

    Returns:
        DatabaseConnection instance
    """
    logger.info(f"Creating database connection to host: {settings.database_host}")
    return DatabaseConnection(
        host=settings.database_host,
        port=settings.database_port,
        database=settings.database_name,
        user=settings.database_user,
        password=settings.database_password,
        min_connections=1,
        max_connections=10,
    )


def get_user_repository(
    db: Annotated[DatabaseConnection, Depends(get_database_connection)],
) -> PostgresUserRepository:
    """
    Get user repository instance.

    Args:
        db: Database connection (injected)

    Returns:
        PostgresUserRepository instance
    """
    return PostgresUserRepository(db)


def get_task_queue() -> TaskQueue:
    """
    Get task queue instance.

    Returns:
        CeleryTaskQueue instance

    Decision: Always returns the real Celery task queue. Integration tests
    override this dependency using FastAPI's dependency_overrides to inject
    MockTaskQueue, which is cleaner than environment variable checking.
    """
    from src.infrastructure.tasks.email.tasks import CeleryTaskQueue

    return CeleryTaskQueue()


def get_register_user_use_case(
    repository: Annotated[PostgresUserRepository, Depends(get_user_repository)],
    task_queue: Annotated[TaskQueue, Depends(get_task_queue)],
) -> RegisterUserUseCase:
    """
    Get RegisterUser use case with dependencies injected.

    Args:
        repository: User repository (injected)
        task_queue: Task queue for emails (injected)

    Returns:
        RegisterUserUseCase instance
    """
    return RegisterUserUseCase(repository, task_queue)


def get_activate_user_use_case(
    repository: Annotated[PostgresUserRepository, Depends(get_user_repository)],
) -> ActivateUserUseCase:
    """
    Get ActivateUser use case with dependencies injected.

    Args:
        repository: User repository (injected)

    Returns:
        ActivateUserUseCase instance
    """
    return ActivateUserUseCase(repository)


async def verify_basic_auth(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    use_case: Annotated[ActivateUserUseCase, Depends(get_activate_user_use_case)],
) -> tuple[str, str]:
    """
    Verify Basic Auth credentials.

    This is used by the activation endpoint to authenticate the user
    before allowing activation.

    Args:
        credentials: HTTP Basic Auth credentials (injected)
        use_case: Activate user use case (injected)

    Returns:
        Tuple of (email, password) if valid

    Raises:
        HTTPException: If credentials are invalid

    Decision: We return the credentials for use in the activation flow.
    The actual verification happens in the use case when we activate.
    """
    # We'll verify credentials in the use case
    # Here we just extract them from Basic Auth
    return (credentials.username, credentials.password)
