"""
Unit tests for User entity.

Tests the business logic for user creation, activation, and password management.
"""

import pytest

from src.domain.exceptions import (
    InvalidActivationCodeError,
    InvalidEmailError,
    UserAlreadyActivatedError,
    WeakPasswordError,
)
from src.domain.user import User


class TestUserCreation:
    """Test user creation logic."""

    def test_create_user_with_valid_data(self) -> None:
        """Test creating a user with valid email and password."""
        user = User.create(email="test@example.com", password="SecurePass123")

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.password_hash != "SecurePass123"  # Should be hashed
        assert not user.is_activated
        assert user.activated_at is None
        assert user.activation_code is not None
        assert len(user.activation_code.code) == 4

    def test_create_user_normalizes_email_to_lowercase(self) -> None:
        """Test that email is normalized to lowercase."""
        user = User.create(email="Test@EXAMPLE.com", password="SecurePass123")

        assert user.email == "test@example.com"

    def test_create_user_with_invalid_email_raises_error(self) -> None:
        """Test that invalid email raises InvalidEmailError."""
        with pytest.raises(InvalidEmailError):
            User.create(email="invalid-email", password="SecurePass123")

        with pytest.raises(InvalidEmailError):
            User.create(email="@example.com", password="SecurePass123")

        with pytest.raises(InvalidEmailError):
            User.create(email="test@", password="SecurePass123")

    def test_create_user_with_weak_password_raises_error(self) -> None:
        """Test that weak password raises WeakPasswordError."""
        with pytest.raises(WeakPasswordError):
            User.create(email="test@example.com", password="short")

        with pytest.raises(WeakPasswordError):
            User.create(email="test@example.com", password="")

    def test_password_is_hashed(self) -> None:
        """Test that password is hashed and not stored in plain text."""
        password = "SecurePass123"
        user = User.create(email="test@example.com", password=password)

        assert user.password_hash != password
        assert len(user.password_hash) > 50  # Bcrypt hashes are long


class TestUserPasswordVerification:
    """Test password verification logic."""

    def test_verify_password_with_correct_password(self) -> None:
        """Test that verify_password returns True for correct password."""
        password = "SecurePass123"
        user = User.create(email="test@example.com", password=password)

        assert user.verify_password(password)

    def test_verify_password_with_incorrect_password(self) -> None:
        """Test that verify_password returns False for incorrect password."""
        user = User.create(email="test@example.com", password="SecurePass123")

        assert not user.verify_password("WrongPassword")
        assert not user.verify_password("securepass123")
        assert not user.verify_password("")


class TestUserActivation:
    """Test user activation logic."""

    def test_activate_with_correct_code(self) -> None:
        """Test that activate succeeds with correct code."""
        user = User.create(email="test@example.com", password="SecurePass123")
        code = user.activation_code.code

        user.activate(code)

        assert user.is_activated
        assert user.activated_at is not None
        assert user.activation_code is None

    def test_activate_with_incorrect_code_raises_error(self) -> None:
        """Test that activate raises error with wrong code."""
        user = User.create(email="test@example.com", password="SecurePass123")

        with pytest.raises(InvalidActivationCodeError):
            user.activate("9999")

    def test_activate_already_activated_user_raises_error(self) -> None:
        """Test that activating an already activated user raises error."""
        user = User.create(email="test@example.com", password="SecurePass123")
        code = user.activation_code.code
        user.activate(code)

        with pytest.raises(UserAlreadyActivatedError):
            user.activate("1234")

    def test_activate_clears_activation_code(self) -> None:
        """Test that activation code is cleared after successful activation."""
        user = User.create(email="test@example.com", password="SecurePass123")
        code = user.activation_code.code

        user.activate(code)

        assert user.activation_code is None


class TestUserActivationCodeRegeneration:
    """Test activation code regeneration."""

    def test_regenerate_activation_code(self) -> None:
        """Test regenerating activation code for non-activated user."""
        user = User.create(email="test@example.com", password="SecurePass123")
        original_code = user.activation_code.code

        new_code = user.regenerate_activation_code()

        assert new_code.code != original_code
        assert user.activation_code == new_code

    def test_regenerate_code_for_activated_user_raises_error(self) -> None:
        """Test that regenerating code for activated user raises error."""
        user = User.create(email="test@example.com", password="SecurePass123")
        code = user.activation_code.code
        user.activate(code)

        with pytest.raises(UserAlreadyActivatedError):
            user.regenerate_activation_code()


class TestUserEquality:
    """Test user equality and hashing."""

    def test_users_with_same_id_are_equal(self) -> None:
        """Test that users with same ID are considered equal."""
        user = User.create(email="test@example.com", password="SecurePass123")
        # Create another user instance with same ID
        user2 = User(
            id=user.id,
            email="different@example.com",
            password_hash="different_hash",
        )

        assert user == user2

    def test_users_with_different_id_are_not_equal(self) -> None:
        """Test that users with different IDs are not equal."""
        user1 = User.create(email="test1@example.com", password="SecurePass123")
        user2 = User.create(email="test2@example.com", password="SecurePass123")

        assert user1 != user2

    def test_user_not_equal_to_non_user(self) -> None:
        """Test that user is not equal to non-User objects."""
        user = User.create(email="test@example.com", password="SecurePass123")

        assert user != "not a user"
        assert user != 123
        assert user is not None

    def test_user_can_be_hashed(self) -> None:
        """Test that users can be hashed (for use in sets/dicts)."""
        user = User.create(email="test@example.com", password="SecurePass123")

        # Should not raise
        hash(user)

        # Should be usable in sets
        user_set = {user}
        assert user in user_set
