"""
Activate User use case.

Handles user account activation with the 4-digit code.
Includes authentication via Basic Auth as per requirements.
"""

from src.domain.exceptions import UserNotFoundError
from src.domain.user_repository import UserRepository


class ActivateUserUseCase:
    """
    Use case for activating a user account.

    This use case handles the activation flow:
    1. Authenticate user (via Basic Auth - email/password)
    2. Verify activation code
    3. Mark user as activated
    4. Persist changes

    Decision: As per requirements, we use Basic Auth (email + password)
    to verify the user's identity before activation. This ensures that
    only the legitimate user can activate their account.
    """

    def __init__(self, user_repository: UserRepository):
        """
        Initialize the use case.

        Args:
            user_repository: Repository for user persistence
        """
        self.user_repository = user_repository

    async def execute(self, email: str, password: str, activation_code: str) -> None:
        """
        Execute the user activation use case.

        Process:
        1. Find user by email
        2. Verify password (Basic Auth)
        3. Verify activation code (must match and not be expired)
        4. Activate user
        5. Save updated user

        Args:
            email: User's email address
            password: User's password (for Basic Auth verification)
            activation_code: The 4-digit code received by email

        Raises:
            UserNotFoundError: If user doesn't exist
            InvalidCredentialsError: If password is incorrect
            UserAlreadyActivatedError: If user is already activated
            InvalidActivationCodeError: If code doesn't match
            ActivationCodeExpiredError: If code expired (>60 seconds)

        Decision: We raise InvalidCredentialsError for wrong password instead of
        returning a boolean to follow the "fail fast" principle and provide
        clear error handling to the presentation layer.
        """
        # Find user
        user = await self.user_repository.find_by_email(email)
        if user is None:
            raise UserNotFoundError(email)

        # Verify password (Basic Auth)
        if not user.verify_password(password):
            raise InvalidCredentialsError()

        # Verify and activate (domain logic handles validation)
        user.activate(activation_code)

        # Persist the changes
        await self.user_repository.save(user)


class InvalidCredentialsError(Exception):
    """Raised when authentication credentials are invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid email or password")
