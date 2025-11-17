"""
Integration tests for user registration endpoint.

Tests the /api/v1/users/register endpoint with:
- Real FastAPI application (TestClient)
- Real database connection
- MockTaskQueue (no Celery worker needed)

Decision: Using pytest instead of Behave for integration tests provides:
- Faster execution
- Better debugging
- pytest fixtures and parametrization
- Single test runner with unit tests
"""

import re


def test_successful_user_registration(api_client, get_mock_tasks):
    """
    Test successful user registration.

    Verifies:
    - 201 Created status
    - User ID in response (valid UUID)
    - Email in response (normalized to lowercase)
    - is_activated is False
    - Success message present
    - Task enqueued to MockTaskQueue
    """
    response = api_client.post(
        "/api/v1/users/register",
        json={"email": "test@example.com", "password": "SecurePass123"},
    )

    # Verify response
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

    data = response.json()
    assert "id" in data, f"No user id in response: {data}"
    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", data["id"]
    ), f"Invalid UUID format: {data['id']}"

    assert data["email"] == "test@example.com", f"Expected test@example.com, got {data['email']}"
    assert data["is_activated"] is False, "User should not be activated"
    assert "message" in data, "No success message in response"

    # Verify task was enqueued
    tasks = get_mock_tasks()
    assert len(tasks) == 1, f"Expected 1 task, got {len(tasks)}"
    assert tasks[0]["email"] == "test@example.com"
    assert len(tasks[0]["code"]) == 4, "Activation code should be 4 digits"


def test_registration_with_duplicate_email(register_user):
    """
    Test registration with email that already exists.

    Verifies:
    - 409 Conflict status
    - UserAlreadyExistsError in response
    """
    # Register first user
    response1 = register_user("existing@example.com", "Pass123First")
    assert response1.status_code == 201

    # Try to register with same email
    response2 = register_user("existing@example.com", "Pass123Second")

    assert (
        response2.status_code == 409
    ), f"Expected 409 Conflict, got {response2.status_code}: {response2.text}"

    data = response2.json()
    detail = data.get("detail", {})
    error_type = detail.get("error", "") if isinstance(detail, dict) else str(detail)

    assert "UserAlreadyExists" in error_type, f"Expected UserAlreadyExists, got {error_type}"


def test_registration_with_invalid_email(api_client):
    """
    Test registration with invalid email format.

    Verifies:
    - 400 Bad Request status
    - InvalidEmailError in response
    """
    response = api_client.post(
        "/api/v1/users/register",
        json={"email": "invalid-email", "password": "SecurePass123"},
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"

    data = response.json()
    detail = data.get("detail", {})
    error_type = detail.get("error", "") if isinstance(detail, dict) else str(detail)

    assert (
        "InvalidEmailError" in error_type or "ValidationError" in error_type
    ), f"Expected InvalidEmailError or ValidationError, got {error_type}"


def test_registration_with_weak_password(api_client):
    """
    Test registration with password that doesn't meet requirements.

    Password must be at least 8 characters.

    Verifies:
    - 400 Bad Request status
    - WeakPasswordError in response
    """
    response = api_client.post(
        "/api/v1/users/register",
        json={"email": "test@example.com", "password": "short"},
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"

    data = response.json()
    detail = data.get("detail", {})
    error_type = detail.get("error", "") if isinstance(detail, dict) else str(detail)

    assert (
        "WeakPasswordError" in error_type or "ValidationError" in error_type
    ), f"Expected WeakPasswordError, got {error_type}"


def test_registration_with_missing_email(api_client):
    """
    Test registration without email field.

    Verifies:
    - 400 Bad Request status (validation error)
    """
    response = api_client.post(
        "/api/v1/users/register",
        json={"password": "SecurePass123"},  # Missing email
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"


def test_registration_with_missing_password(api_client):
    """
    Test registration without password field.

    Verifies:
    - 400 Bad Request status (validation error)
    """
    response = api_client.post(
        "/api/v1/users/register",
        json={"email": "test@example.com"},  # Missing password
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"


def test_email_normalization_to_lowercase(api_client, get_mock_tasks):
    """
    Test that email addresses are normalized to lowercase.

    Verifies:
    - Mixed case email is stored as lowercase
    - Task is enqueued with lowercase email
    """
    response = api_client.post(
        "/api/v1/users/register",
        json={"email": "Test@Example.COM", "password": "SecurePass123"},
    )

    assert response.status_code == 201

    data = response.json()
    assert (
        data["email"] == "test@example.com"
    ), f"Email should be normalized to lowercase, got {data['email']}"

    # Verify task has lowercase email
    tasks = get_mock_tasks()
    assert tasks[0]["email"] == "test@example.com"
