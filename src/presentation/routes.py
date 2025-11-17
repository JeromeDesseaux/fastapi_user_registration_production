"""
FastAPI routes for user registration and activation.

This module defines the HTTP API endpoints following REST principles.
Each route is thin - it just handles HTTP concerns and delegates to use cases.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.application.activate_user import ActivateUserUseCase, InvalidCredentialsError
from src.application.register_user import RegisterUserUseCase
from src.domain.exceptions import (
    ActivationCodeExpiredError,
    DomainError,
    InvalidActivationCodeError,
    InvalidEmailError,
    UserAlreadyActivatedError,
    UserAlreadyExistsError,
    UserNotFoundError,
    WeakPasswordError,
)
from src.infrastructure.rate_limiting.dependencies import (
    check_activation_rate_limit,
    check_registration_rate_limit,
)
from src.presentation.dependencies import (
    get_activate_user_use_case,
    get_register_user_use_case,
    verify_basic_auth,
)
from src.presentation.schemas import (
    ActivateUserRequest,
    ActivateUserResponse,
    ErrorResponse,
    HealthCheckResponse,
    RegisterUserRequest,
    RegisterUserResponse,
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["users"])


@router.post(
    "/users/register",
    response_model=RegisterUserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User registered successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        409: {"model": ErrorResponse, "description": "User already exists"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Register a new user",
    description="""
    Register a new user with email and password.

    A 4-digit activation code will be sent to the provided email.
    The code expires in 60 seconds.

    Business Rules:
    - Email must be valid and unique
    - Password must be at least 8 characters
    - Activation code is generated automatically
    - Email is sent asynchronously via Celery
    """,
)
async def register_user(
    request: RegisterUserRequest,
    use_case: Annotated[RegisterUserUseCase, Depends(get_register_user_use_case)],
    _rate_limit: Annotated[None, Depends(check_registration_rate_limit)] = None,
) -> RegisterUserResponse:
    """
    Register a new user.

    Decision: We return 201 Created on success as this creates a new resource.
    The response includes the user ID and creation timestamp for client reference.
    """
    try:
        user = await use_case.execute(email=str(request.email), password=request.password)

        return RegisterUserResponse(
            id=user.id,
            email=user.email,
            is_activated=user.is_activated,
            created_at=user.created_at,
            message="User registered successfully. Check your email for the activation code.",
        )

    except UserAlreadyExistsError as e:
        logger.warning(f"Registration failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "UserAlreadyExists", "message": str(e)},
        ) from e

    except InvalidEmailError as e:
        logger.warning(f"Registration failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "InvalidEmail", "message": str(e)},
        ) from e

    except WeakPasswordError as e:
        logger.warning(f"Registration failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "WeakPassword", "message": str(e)},
        ) from e

    except DomainError as e:
        logger.error(f"Domain error during registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "DomainError", "message": str(e)},
        ) from e

    except Exception as e:
        logger.error(f"Unexpected error during registration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalError",
                "message": "An unexpected error occurred",
            },
        ) from e


@router.post(
    "/users/activate",
    response_model=ActivateUserResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Account activated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid activation code"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        404: {"model": ErrorResponse, "description": "User not found"},
        409: {"model": ErrorResponse, "description": "User already activated"},
        410: {"model": ErrorResponse, "description": "Activation code expired"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Activate user account",
    description="""
    Activate a user account with the 4-digit code received by email.

    Authentication: HTTP Basic Auth (email:password)

    Business Rules:
    - User must exist
    - Credentials must be valid (Basic Auth)
    - Activation code must match
    - Code must not be expired (60 seconds)
    - User must not be already activated
    """,
)
async def activate_user(
    http_request: Request,
    request: ActivateUserRequest,
    credentials: Annotated[tuple[str, str], Depends(verify_basic_auth)],
    use_case: Annotated[ActivateUserUseCase, Depends(get_activate_user_use_case)],
) -> ActivateUserResponse:
    """
    Activate a user account.

    Decision: We use HTTP Basic Auth as specified in requirements.
    This is simple and appropriate for this use case. In production,
    we might use JWT tokens, but Basic Auth meets the requirements.
    """
    email, password = credentials

    # Check activation rate limit (per email)
    await check_activation_rate_limit(http_request, email)

    try:
        # Execute activation use case
        await use_case.execute(
            email=email, password=password, activation_code=request.activation_code
        )

        # Fetch updated user to get activation timestamp
        user = await use_case.user_repository.find_by_email(email)

        # User must exist since activation just succeeded
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalError",
                    "message": "User not found after activation",
                },
            )

        return ActivateUserResponse(
            email=user.email,
            is_activated=user.is_activated,
            activated_at=user.activated_at,
            message="Account activated successfully",
        )

    except UserNotFoundError as e:
        logger.warning(f"Activation failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "UserNotFound", "message": str(e)},
        ) from e

    except InvalidCredentialsError as e:
        logger.warning(f"Activation failed: Invalid credentials for {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "InvalidCredentials", "message": str(e)},
            headers={"WWW-Authenticate": "Basic"},
        ) from e

    except UserAlreadyActivatedError as e:
        logger.warning(f"Activation failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "UserAlreadyActivated", "message": str(e)},
        ) from e

    except InvalidActivationCodeError as e:
        logger.warning(f"Activation failed: Invalid code for {email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "InvalidActivationCode", "message": str(e)},
        ) from e

    except ActivationCodeExpiredError as e:
        logger.warning(f"Activation failed: Code expired for {email}")
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "error": "ActivationCodeExpired",
                "message": str(e),
                "hint": "Request a new activation code",
            },
        ) from e

    except DomainError as e:
        logger.error(f"Domain error during activation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "DomainError", "message": str(e)},
        ) from e

    except Exception as e:
        logger.error(f"Unexpected error during activation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalError",
                "message": "An unexpected error occurred",
            },
        ) from e


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check if the service is running and healthy",
    tags=["health"],
)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint.

    Decision: Essential for production deployments, container orchestration,
    and monitoring. Shows service is responsive and provides basic metadata.
    """
    return HealthCheckResponse(
        status="healthy",
        service="user-registration-api",
        version="1.0.0",
        timestamp=datetime.now(UTC),
    )


# ================================================================================================
# TESTING NOTES
# ================================================================================================
# Decision: Integration tests use FastAPI's dependency_overrides to inject MockTaskQueue
# instead of environment variable checks. This is cleaner and more aligned with FastAPI patterns.
