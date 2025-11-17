"""
Mock implementation of TaskQueue for integration testing.

This mock stores enqueued tasks in memory instead of sending them to Celery.
Allows fast integration tests without requiring Redis, Celery workers, or Mailhog.

Decision: Using class-level storage to maintain state across multiple instances.
This works because FastAPI dependency injection may create new instances per request.
"""

import logging
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class MockTaskQueue:
    """
    Mock task queue that stores tasks in memory.

    Implements the TaskQueue protocol from src.application.register_user.
    Used in integration tests to avoid running real Celery workers.
    """

    # Class-level storage shared across all instances
    _tasks: ClassVar[list[dict[str, Any]]] = []
    _task_counter: ClassVar[int] = 0

    def enqueue_send_activation_email(self, email: str, code: str) -> str:
        """
        Mock enqueue operation - stores task in memory.

        Args:
            email: Recipient email address
            code: 4-digit activation code

        Returns:
            Mock task ID for tracking

        Decision: We store the task data so integration tests can verify
        that the correct email and code were enqueued.
        """
        MockTaskQueue._task_counter += 1
        task_id = f"mock-task-{MockTaskQueue._task_counter}"

        task_data = {
            "task_id": task_id,
            "email": email,
            "code": code,
            "status": "enqueued",
        }

        MockTaskQueue._tasks.append(task_data)
        logger.info(f"[MOCK] Enqueued email task {task_id} for {email}")

        return task_id

    @classmethod
    def get_all_tasks(cls) -> list[dict[str, Any]]:
        """
        Get all enqueued tasks.

        Returns:
            List of all tasks that have been enqueued

        Decision: This is used by integration tests to verify tasks were enqueued.
        """
        return cls._tasks.copy()

    @classmethod
    def get_task_for_email(cls, email: str) -> dict[str, Any] | None:
        """
        Get the most recent task for a specific email.

        Args:
            email: Email address to search for

        Returns:
            Task data if found, None otherwise

        Decision: Helper method for integration tests to easily find tasks by email.
        """
        for task in reversed(cls._tasks):  # Search from most recent
            if task["email"] == email:
                return task
        return None

    @classmethod
    def clear(cls) -> None:
        """
        Clear all stored tasks.

        Decision: Called between test scenarios to ensure isolation.
        Each test scenario starts with a clean slate.
        """
        cls._tasks = []
        cls._task_counter = 0
        logger.info("[MOCK] Cleared all tasks")

    @classmethod
    def get_task_count(cls) -> int:
        """Get the number of enqueued tasks."""
        return len(cls._tasks)
