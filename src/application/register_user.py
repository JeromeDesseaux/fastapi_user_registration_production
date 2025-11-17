"""
Register User use case.

Orchestrates the user registration process including:
1. Creating a new user
2. Persisting to the database
3. Sending activation code via email (asynchronously via Celery)

This use case coordinates between domain entities and infrastructure services.
"""

from typing import Protocol

from src.domain.exceptions import UserAlreadyExistsError
from src.domain.user import User
from src.domain.user_repository import UserRepository


class TaskQueue(Protocol):
    """
    Protocol for task queue operations.

    This allows the use case to remain agnostic of the specific
    task queue implementation (Celery, in our case).
    """

    def enqueue_send_activation_email(self, email: str, code: str) -> str:
        """
        Enqueue a task to send an activation email.

        Args:
            email: Recipient email
            code: Activation code

        Returns:
            Task ID for tracking
        """
        ...


class RegisterUserUseCase:
    """
    Use case for registering a new user.

    This class encapsulates the business logic for user registration,
    coordinating between the domain layer and infrastructure services.

    Decision: We use dependency injection for all external dependencies
    (repository, task queue) to maintain testability and follow SOLID principles.
    """

    def __init__(self, user_repository: UserRepository, task_queue: TaskQueue):
        """
        Initialize the use case.

        Args:
            user_repository: Repository for user persistence
            task_queue: Task queue for asynchronous email sending
        """
        self.user_repository = user_repository
        self.task_queue = task_queue

    async def execute(self, email: str, password: str) -> User:
        """
        Execute the user registration use case.

        Process:
        1. Check if user already exists
        2. Create new user entity (generates activation code)
        3. Save user to database
        4. Enqueue email sending task (Celery)

        Args:
            email: User's email address
            password: User's password (plain text, will be hashed by domain)

        Returns:
            The created User entity

        Raises:
            UserAlreadyExistsError: If a user with this email already exists
            InvalidEmailError: If email format is invalid
            WeakPasswordError: If password doesn't meet requirements

        Decision: Email sending is async (via Celery) to:
        - Avoid blocking the API response
        - Allow retries if the email service is temporarily down
        - Improve user experience (faster response)
        - Handle failures gracefully without affecting registration
        """
        # Check if user already exists
        if await self.user_repository.exists_by_email(email):
            raise UserAlreadyExistsError(email)

        # Create new user (domain logic handles validation and code generation)
        user = User.create(email=email, password=password)

        # Persist the user
        await self.user_repository.save(user)

        # Enqueue email sending task (async via Celery)
        # This returns immediately, actual sending happens in background
        if user.activation_code:
            task_id = self.task_queue.enqueue_send_activation_email(
                email=user.email, code=user.activation_code.code
            )
            # In a production system, we log the task_id for monitoring
            print(f"Enqueued email task with ID: {task_id}")

        return user
