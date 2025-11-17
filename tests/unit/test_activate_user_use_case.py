"""
Unit tests for ActivateUser use case.

Tests the orchestration logic for user activation.
Uses mocks for dependencies to isolate the use case.
"""

from unittest.mock import AsyncMock

import pytest

from src.application.activate_user import ActivateUserUseCase, InvalidCredentialsError
from src.domain.exceptions import (
    InvalidActivationCodeError,
    UserAlreadyActivatedError,
    UserNotFoundError,
)
from src.domain.user import User


class TestActivateUserUseCase:
    """Test ActivateUser use case."""

    @pytest.fixture
    def mock_repository(self) -> AsyncMock:
        """Create a mock user repository."""
        repository = AsyncMock()
        return repository

    @pytest.fixture
    def use_case(self, mock_repository: AsyncMock) -> ActivateUserUseCase:
        """Create an ActivateUserUseCase with mocked repository."""
        return ActivateUserUseCase(mock_repository)

    @pytest.mark.asyncio
    async def test_activate_user_success(
        self, use_case: ActivateUserUseCase, mock_repository: AsyncMock
    ) -> None:
        """Test successful user activation."""
        # Create a user
        user = User.create(email="test@example.com", password="SecurePass123")
        activation_code = user.activation_code.code

        # Mock repository to return the user
        mock_repository.find_by_email = AsyncMock(return_value=user)
        mock_repository.save = AsyncMock()

        # Execute activation
        await use_case.execute(
            email="test@example.com",
            password="SecurePass123",
            activation_code=activation_code,
        )

        # Verify user was activated
        assert user.is_activated
        assert user.activated_at is not None
        assert user.activation_code is None

        # Verify repository was called
        mock_repository.find_by_email.assert_called_once_with("test@example.com")
        mock_repository.save.assert_called_once_with(user)

    @pytest.mark.asyncio
    async def test_activate_user_not_found(
        self, use_case: ActivateUserUseCase, mock_repository: AsyncMock
    ) -> None:
        """Test activation fails when user doesn't exist."""
        mock_repository.find_by_email = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundError):
            await use_case.execute(
                email="nonexistent@example.com",
                password="SecurePass123",
                activation_code="1234",
            )

        # Save should not be called
        mock_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_user_wrong_password(
        self, use_case: ActivateUserUseCase, mock_repository: AsyncMock
    ) -> None:
        """Test activation fails with wrong password."""
        user = User.create(email="test@example.com", password="SecurePass123")
        mock_repository.find_by_email = AsyncMock(return_value=user)

        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(
                email="test@example.com",
                password="WrongPassword",
                activation_code="1234",
            )

        # Save should not be called
        mock_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_user_wrong_code(
        self, use_case: ActivateUserUseCase, mock_repository: AsyncMock
    ) -> None:
        """Test activation fails with wrong code."""
        user = User.create(email="test@example.com", password="SecurePass123")
        mock_repository.find_by_email = AsyncMock(return_value=user)

        with pytest.raises(InvalidActivationCodeError):
            await use_case.execute(
                email="test@example.com",
                password="SecurePass123",
                activation_code="9999",
            )

        # User should not be activated
        assert not user.is_activated
        # Save should not be called
        mock_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_already_activated_user(
        self, use_case: ActivateUserUseCase, mock_repository: AsyncMock
    ) -> None:
        """Test activation fails for already activated user."""
        user = User.create(email="test@example.com", password="SecurePass123")
        code = user.activation_code.code
        user.activate(code)  # Activate the user

        mock_repository.find_by_email = AsyncMock(return_value=user)

        with pytest.raises(UserAlreadyActivatedError):
            await use_case.execute(
                email="test@example.com",
                password="SecurePass123",
                activation_code="1234",
            )

        # Save should not be called
        mock_repository.save.assert_not_called()
