"""
Integration tests for user activation endpoint.

Tests the /api/v1/users/activate endpoint with:
- Real FastAPI application (TestClient)
- Real database connection
- MockTaskQueue for activation codes
- Basic Auth for authentication

Decision: Using pytest instead of Behave for faster, more flexible integration tests.
"""

import base64


def test_successful_account_activation(api_client, register_user, get_activation_code_from_queue):
    """
    Test successful account activation.

    Verifies:
    - User can activate with correct code and credentials
    - 200 OK status
    - Success message in response
    """
    # Register a user
    email = "test@example.com"
    password = "SecurePass123"
    response = register_user(email, password)
    assert response.status_code == 201

    # Get activation code from mock queue
    activation_code = get_activation_code_from_queue(email)

    # Prepare Basic Auth header
    credentials = f"{email}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    headers = {"Authorization": f"Basic {encoded}"}

    # Activate account
    response = api_client.post(
        "/api/v1/users/activate",
        json={"activation_code": activation_code},
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "message" in data, "No success message in response"


def test_activation_with_wrong_code(api_client, register_user, get_activation_code_from_queue):
    """
    Test activation with incorrect activation code.

    Verifies:
    - 400 Bad Request status
    - InvalidActivationCodeError in response
    """
    # Register a user
    email = "test@example.com"
    password = "SecurePass123"
    response = register_user(email, password)
    assert response.status_code == 201

    # Use wrong code
    wrong_code = "9999"

    # Prepare Basic Auth
    credentials = f"{email}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    headers = {"Authorization": f"Basic {encoded}"}

    # Try to activate with wrong code
    response = api_client.post(
        "/api/v1/users/activate",
        json={"activation_code": wrong_code},
        headers=headers,
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"

    data = response.json()
    detail = data.get("detail", {})
    error_type = detail.get("error", "") if isinstance(detail, dict) else str(detail)

    assert (
        "InvalidActivationCode" in error_type
    ), f"Expected InvalidActivationCode, got {error_type}"


def test_activation_with_wrong_password(api_client, register_user, get_activation_code_from_queue):
    """
    Test activation with correct code but wrong password (invalid credentials).

    Verifies:
    - 401 Unauthorized status
    - Invalid credentials error
    """
    # Register a user
    email = "test@example.com"
    password = "SecurePass123"
    response = register_user(email, password)
    assert response.status_code == 201

    # Get correct activation code
    activation_code = get_activation_code_from_queue(email)

    # Use wrong password
    credentials = f"{email}:WrongPassword123"
    encoded = base64.b64encode(credentials.encode()).decode()
    headers = {"Authorization": f"Basic {encoded}"}

    # Try to activate with wrong password
    response = api_client.post(
        "/api/v1/users/activate",
        json={"activation_code": activation_code},
        headers=headers,
    )

    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"


def test_activation_of_non_existent_user(api_client):
    """
    Test activation of a user that doesn't exist.

    Verifies:
    - 404 Not Found status
    - UserNotFoundError in response
    """
    email = "nonexistent@example.com"
    password = "SomePass123"

    credentials = f"{email}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    headers = {"Authorization": f"Basic {encoded}"}

    response = api_client.post(
        "/api/v1/users/activate",
        json={"activation_code": "1234"},
        headers=headers,
    )

    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

    data = response.json()
    detail = data.get("detail", {})
    error_type = detail.get("error", "") if isinstance(detail, dict) else str(detail)

    assert "UserNotFound" in error_type, f"Expected UserNotFound, got {error_type}"


def test_activation_of_already_activated_user(
    api_client, register_user, get_activation_code_from_queue
):
    """
    Test activation of a user that is already activated.

    Verifies:
    - 409 Conflict status
    - UserAlreadyActivatedError in response
    """
    # Register and activate a user
    email = "test@example.com"
    password = "SecurePass123"
    response = register_user(email, password)
    assert response.status_code == 201

    # Get activation code
    activation_code = get_activation_code_from_queue(email)

    # Prepare Basic Auth
    credentials = f"{email}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    headers = {"Authorization": f"Basic {encoded}"}

    # Activate once
    response = api_client.post(
        "/api/v1/users/activate",
        json={"activation_code": activation_code},
        headers=headers,
    )
    assert response.status_code == 200

    # Try to activate again
    response = api_client.post(
        "/api/v1/users/activate",
        json={"activation_code": activation_code},  # Same code or any code
        headers=headers,
    )

    assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"

    data = response.json()
    detail = data.get("detail", {})
    error_type = detail.get("error", "") if isinstance(detail, dict) else str(detail)

    assert "UserAlreadyActivated" in error_type, f"Expected UserAlreadyActivated, got {error_type}"


def test_activation_without_auth_header(api_client, register_user):
    """
    Test activation without providing Basic Auth credentials.

    Verifies:
    - 401 Unauthorized status
    """
    # Register a user
    email = "test@example.com"
    password = "SecurePass123"
    response = register_user(email, password)
    assert response.status_code == 201

    # Try to activate without auth header
    response = api_client.post(
        "/api/v1/users/activate",
        json={"activation_code": "1234"},
        # No headers
    )

    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
