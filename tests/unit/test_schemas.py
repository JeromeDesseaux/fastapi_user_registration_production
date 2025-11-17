"""
Tests for Pydantic schemas (presentation layer).

These tests verify request/response schema validation.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.presentation.schemas import (
    ActivateUserRequest,
    ActivateUserResponse,
    RegisterUserRequest,
    RegisterUserResponse,
)


class TestRegisterUserRequest:
    """Tests for registration request schema."""

    def test_valid_registration(self):
        """Test valid registration data."""
        data = RegisterUserRequest(email="test@example.com", password="SecurePass123")

        assert data.email == "test@example.com"
        assert data.password == "SecurePass123"

    def test_invalid_email(self):
        """Test invalid email format."""
        with pytest.raises(ValidationError):
            RegisterUserRequest(email="invalid-email", password="SecurePass123")

    def test_missing_email(self):
        """Test missing email field."""
        with pytest.raises(ValidationError):
            RegisterUserRequest(password="SecurePass123")

    def test_missing_password(self):
        """Test missing password field."""
        with pytest.raises(ValidationError):
            RegisterUserRequest(email="test@example.com")

    def test_email_normalization(self):
        """Test email is normalized to lowercase."""
        data = RegisterUserRequest(email="Test@EXAMPLE.COM", password="SecurePass123")

        # Pydantic EmailStr normalizes to lowercase
        assert data.email.lower() == "test@example.com"


class TestActivateUserRequest:
    """Tests for activation request schema."""

    def test_valid_activation_code(self):
        """Test valid activation code."""
        data = ActivateUserRequest(activation_code="1234")

        assert data.activation_code == "1234"

    def test_missing_activation_code(self):
        """Test missing activation code."""
        with pytest.raises(ValidationError):
            ActivateUserRequest()

    def test_empty_activation_code(self):
        """Test empty activation code."""
        with pytest.raises(ValidationError):
            ActivateUserRequest(activation_code="")


class TestRegisterUserResponse:
    """Tests for registration response schema."""

    def test_register_response(self):
        """Test registration response schema."""
        data = RegisterUserResponse(
            id=uuid4(),
            email="test@example.com",
            is_activated=False,
            created_at=datetime.now(UTC),
            message="User registered successfully",
        )

        assert data.is_activated is False
        assert data.email == "test@example.com"
        assert "registered" in data.message.lower()

    def test_register_response_serialization(self):
        """Test registration response can be serialized to dict."""
        user_id = uuid4()
        data = RegisterUserResponse(
            id=user_id,
            email="test@example.com",
            is_activated=False,
            created_at=datetime.now(UTC),
            message="User registered successfully",
        )

        result = data.model_dump()

        assert result["id"] == user_id
        assert result["email"] == "test@example.com"


class TestActivateUserResponse:
    """Tests for activation response schema."""

    def test_activate_response(self):
        """Test activation response schema."""
        now = datetime.now(UTC)
        data = ActivateUserResponse(
            email="test@example.com",
            is_activated=True,
            activated_at=now,
            message="Account activated successfully",
        )

        assert data.is_activated is True
        assert data.activated_at is not None
        assert "activated" in data.message.lower()

    def test_activate_response_serialization(self):
        """Test activation response can be serialized to dict."""
        now = datetime.now(UTC)
        data = ActivateUserResponse(
            email="test@example.com",
            is_activated=True,
            activated_at=now,
            message="Account activated successfully",
        )

        result = data.model_dump()

        assert result["email"] == "test@example.com"
        assert result["is_activated"] is True
