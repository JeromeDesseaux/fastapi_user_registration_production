"""
Tests for API routes (presentation layer).

These tests verify the API endpoints with mocked dependencies.
"""

import base64
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.application.activate_user import InvalidCredentialsError
from src.domain.activation_code import ActivationCode
from src.domain.exceptions import (
    ActivationCodeExpiredError,
    InvalidActivationCodeError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from src.domain.user import User
from src.main import app


@pytest.fixture
def mock_register_use_case():
    """Create mock register use case."""
    mock = Mock()
    mock.execute = AsyncMock()
    return mock


@pytest.fixture
def mock_activate_use_case():
    """Create mock activate use case."""
    mock = Mock()
    mock.execute = AsyncMock()
    # The route accesses use_case.user_repository directly
    mock_repo = Mock()
    mock_repo.find_by_email = AsyncMock()
    mock.user_repository = mock_repo
    return mock


@pytest.fixture
def client(mock_register_use_case, mock_activate_use_case):
    """Create test client with mocked dependencies."""
    from src.presentation.dependencies import (
        get_activate_user_use_case,
        get_register_user_use_case,
    )

    app.dependency_overrides[get_register_user_use_case] = lambda: mock_register_use_case
    app.dependency_overrides[get_activate_user_use_case] = lambda: mock_activate_use_case

    yield TestClient(app)

    # Clean up
    app.dependency_overrides = {}


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestRegisterEndpoint:
    """Tests for user registration endpoint."""

    def test_register_success(self, client, mock_register_use_case):
        """Test successful user registration."""
        # Create a mock user
        activation_code = ActivationCode.generate(60)
        mock_user = User(
            id=uuid4(),
            email="test@example.com",
            password_hash="hashed",
            is_activated=False,
            created_at=datetime.now(UTC),
            activated_at=None,
            activation_code=activation_code,
        )

        mock_register_use_case.execute.return_value = mock_user

        response = client.post(
            "/api/v1/users/register",
            json={"email": "test@example.com", "password": "SecurePass123"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["is_activated"] is False
        assert "id" in data

    def test_register_duplicate_email(self, client, mock_register_use_case):
        """Test registration with duplicate email returns 409."""
        mock_register_use_case.execute.side_effect = UserAlreadyExistsError("test@example.com")

        response = client.post(
            "/api/v1/users/register",
            json={"email": "test@example.com", "password": "SecurePass123"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "already exists" in data["detail"]["message"].lower()

    def test_register_invalid_email(self, client):
        """Test registration with invalid email returns 400."""
        response = client.post(
            "/api/v1/users/register",
            json={"email": "invalid-email", "password": "SecurePass123"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_weak_password(self, client):
        """Test registration with weak password returns 400."""
        response = client.post(
            "/api/v1/users/register",
            json={"email": "test@example.com", "password": "123"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_missing_fields(self, client):
        """Test registration with missing fields returns 400."""
        response = client.post(
            "/api/v1/users/register",
            json={"email": "test@example.com"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestActivateEndpoint:
    """Tests for user activation endpoint."""

    def test_activate_success(self, client, mock_activate_use_case):
        """Test successful activation."""
        mock_user = User(
            id=uuid4(),
            email="test@example.com",
            password_hash="hashed",
            is_activated=True,
            created_at=datetime.now(UTC),
            activated_at=datetime.now(UTC),
            activation_code=None,
        )

        # Mock the use case execution and repository find
        mock_activate_use_case.execute.return_value = None
        mock_activate_use_case.user_repository.find_by_email.return_value = mock_user

        auth = base64.b64encode(b"test@example.com:SecurePass123").decode()
        response = client.post(
            "/api/v1/users/activate",
            json={"activation_code": "1234"},
            headers={"Authorization": f"Basic {auth}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_activated"] is True
        assert data["activated_at"] is not None

    def test_activate_invalid_code(self, client, mock_activate_use_case):
        """Test activation with invalid code returns 400."""
        mock_activate_use_case.execute.side_effect = InvalidActivationCodeError()

        auth = base64.b64encode(b"test@example.com:SecurePass123").decode()
        response = client.post(
            "/api/v1/users/activate",
            json={"activation_code": "9999"},
            headers={"Authorization": f"Basic {auth}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_activate_expired_code(self, client, mock_activate_use_case):
        """Test activation with expired code returns 410 Gone."""
        mock_activate_use_case.execute.side_effect = ActivationCodeExpiredError()

        auth = base64.b64encode(b"test@example.com:SecurePass123").decode()
        response = client.post(
            "/api/v1/users/activate",
            json={"activation_code": "1234"},
            headers={"Authorization": f"Basic {auth}"},
        )

        assert response.status_code == status.HTTP_410_GONE

    def test_activate_invalid_credentials(self, client, mock_activate_use_case):
        """Test activation with wrong password returns 401."""
        mock_activate_use_case.execute.side_effect = InvalidCredentialsError()

        auth = base64.b64encode(b"test@example.com:WrongPassword").decode()
        response = client.post(
            "/api/v1/users/activate",
            json={"activation_code": "1234"},
            headers={"Authorization": f"Basic {auth}"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_activate_user_not_found(self, client, mock_activate_use_case):
        """Test activation with non-existent user returns 404."""
        mock_activate_use_case.execute.side_effect = UserNotFoundError("test@example.com")

        auth = base64.b64encode(b"test@example.com:SecurePass123").decode()
        response = client.post(
            "/api/v1/users/activate",
            json={"activation_code": "1234"},
            headers={"Authorization": f"Basic {auth}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_activate_missing_auth(self, client):
        """Test activation without auth header returns 401."""
        response = client.post(
            "/api/v1/users/activate",
            json={"activation_code": "1234"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_activate_invalid_auth_format(self, client):
        """Test activation with invalid auth format returns 401."""
        response = client.post(
            "/api/v1/users/activate",
            json={"activation_code": "1234"},
            headers={"Authorization": "InvalidFormat"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_activate_missing_code(self, client):
        """Test activation without code returns 400."""
        auth = base64.b64encode(b"test@example.com:SecurePass123").decode()
        response = client.post(
            "/api/v1/users/activate",
            json={},
            headers={"Authorization": f"Basic {auth}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
