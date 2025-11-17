"""
Unit tests for RegisterUser use case.

Tests the orchestration logic for user registration.
Uses mocks for dependencies to isolate the use case.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.register_user import RegisterUserUseCase
from src.domain.exceptions import UserAlreadyExistsError


class TestRegisterUserUseCase:
    """Test RegisterUser use case."""

    @pytest.fixture
    def mock_repository(self) -> AsyncMock:
        """Create a mock user repository."""
        repository = AsyncMock()
        repository.exists_by_email = AsyncMock(return_value=False)
        repository.save = AsyncMock()
        return repository

    @pytest.fixture
    def mock_task_queue(self) -> MagicMock:
        """Create a mock task queue."""
        task_queue = MagicMock()
        task_queue.enqueue_send_activation_email = MagicMock(return_value="task-123")
        return task_queue

    @pytest.fixture
    def use_case(
        self, mock_repository: AsyncMock, mock_task_queue: MagicMock
    ) -> RegisterUserUseCase:
        """Create a RegisterUserUseCase with mocked dependencies."""
        return RegisterUserUseCase(mock_repository, mock_task_queue)

    @pytest.mark.asyncio
    async def test_register_user_success(
        self,
        use_case: RegisterUserUseCase,
        mock_repository: AsyncMock,
        mock_task_queue: MagicMock,
    ) -> None:
        """Test successful user registration."""
        email = "test@example.com"
        password = "SecurePass123"

        user = await use_case.execute(email, password)

        # Verify user was created correctly
        assert user.email == email.lower()
        assert user.verify_password(password)
        assert not user.is_activated
        assert user.activation_code is not None

        # Verify repository was called
        mock_repository.exists_by_email.assert_called_once_with(email)
        mock_repository.save.assert_called_once()

        # Verify email task was enqueued
        mock_task_queue.enqueue_send_activation_email.assert_called_once_with(
            email=user.email, code=user.activation_code.code
        )

    @pytest.mark.asyncio
    async def test_register_user_already_exists(
        self, use_case: RegisterUserUseCase, mock_repository: AsyncMock
    ) -> None:
        """Test registration fails when user already exists."""
        mock_repository.exists_by_email = AsyncMock(return_value=True)
        email = "existing@example.com"

        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await use_case.execute(email, "SecurePass123")

        assert exc_info.value.email == email
        # Save should not be called
        mock_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_user_normalizes_email(
        self, use_case: RegisterUserUseCase, mock_repository: AsyncMock
    ) -> None:
        """Test that email is normalized to lowercase."""
        email = "Test@EXAMPLE.com"
        user = await use_case.execute(email, "SecurePass123")

        assert user.email == "test@example.com"
        mock_repository.exists_by_email.assert_called_once_with(email)

    @pytest.mark.asyncio
    async def test_register_user_generates_activation_code(
        self, use_case: RegisterUserUseCase
    ) -> None:
        """Test that activation code is generated."""
        user = await use_case.execute("test@example.com", "SecurePass123")

        assert user.activation_code is not None
        assert len(user.activation_code.code) == 4
        assert user.activation_code.code.isdigit()
