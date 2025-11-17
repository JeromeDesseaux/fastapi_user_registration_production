"""
User entity.

Represents the User aggregate root in our domain model.
Contains business logic for user registration and activation.
"""

import re
import uuid
from datetime import UTC, datetime

import bcrypt

from src.domain.activation_code import ActivationCode
from src.domain.exceptions import (
    InvalidEmailError,
    UserAlreadyActivatedError,
    WeakPasswordError,
)

# Password hashing configuration
# Cost factor 12 balances security and performance (2^12 = 4096 iterations)
BCRYPT_ROUNDS = 12


class User:
    """
    User aggregate root.

    Represents a user in the system with registration and activation capabilities.
    This entity encapsulates all business rules related to users.

    Attributes:
        id: Unique identifier for the user
        email: User's email address (unique)
        password_hash: Hashed password
        is_activated: Whether the user has verified their email
        created_at: When the user was created
        activated_at: When the user activated their account (None if not activated)
        activation_code: Current activation code (None if already activated)
    """

    # Email validation regex
    # Simple but effective pattern for most valid emails
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    # Password requirements
    MIN_PASSWORD_LENGTH = 8

    def __init__(
        self,
        id: uuid.UUID,
        email: str,
        password_hash: str,
        is_activated: bool = False,
        created_at: datetime | None = None,
        activated_at: datetime | None = None,
        activation_code: ActivationCode | None = None,
    ):
        """
        Initialize a User entity.

        Args:
            id: Unique identifier
            email: User's email
            password_hash: Hashed password
            is_activated: Activation status
            created_at: Creation timestamp
            activated_at: Activation timestamp
            activation_code: Current activation code

        Note: This constructor is primarily for reconstructing entities from persistence.
        Use the 'create' class method for creating new users.
        """
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.is_activated = is_activated
        self.created_at = created_at or datetime.now(UTC)
        self.activated_at = activated_at
        self.activation_code = activation_code

    @classmethod
    def create(cls, email: str, password: str) -> "User":
        """
        Create a new user with email and password.

        This is a factory method that enforces business rules for user creation.

        Args:
            email: User's email address
            password: Plain text password (will be hashed)

        Returns:
            A new User entity with generated ID and activation code

        Raises:
            InvalidEmailError: If email format is invalid
            WeakPasswordError: If password doesn't meet requirements

        Decision: We generate both the user ID and activation code here to ensure
        a complete, valid aggregate is always created. The activation code is generated
        immediately so it can be sent to the user right after registration.
        """
        # Validate email format
        if not cls._is_valid_email(email):
            raise InvalidEmailError(email)

        # Validate password strength
        if len(password) < cls.MIN_PASSWORD_LENGTH:
            raise WeakPasswordError(
                f"Password must be at least {cls.MIN_PASSWORD_LENGTH} characters long"
            )

        # Hash the password using bcrypt
        # bcrypt handles salting automatically
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        password_hash = bcrypt.hashpw(password_bytes, salt).decode("utf-8")

        # Generate activation code (60 seconds expiry as per requirements)
        activation_code = ActivationCode.generate(expires_in_seconds=60)

        return cls(
            id=uuid.uuid4(),
            email=email.lower(),  # Normalize email to lowercase
            password_hash=password_hash,
            is_activated=False,
            created_at=datetime.now(UTC),
            activated_at=None,
            activation_code=activation_code,
        )

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """
        Validate email format.

        Args:
            email: Email to validate

        Returns:
            True if valid, False otherwise
        """
        return bool(User.EMAIL_REGEX.match(email))

    def verify_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.

        Used for Basic Auth during activation.

        Args:
            password: Plain text password to verify

        Returns:
            True if password matches, False otherwise
        """
        password_bytes = password.encode("utf-8")
        hash_bytes = self.password_hash.encode("utf-8")
        is_pwd_match: bool = bcrypt.checkpw(password_bytes, hash_bytes)
        return is_pwd_match

    def activate(self, provided_code: str) -> None:
        """
        Activate the user account with the provided code.

        This method encapsulates the business logic for account activation.

        Args:
            provided_code: The 4-digit code provided by the user

        Raises:
            UserAlreadyActivatedError: If the user is already activated
            InvalidActivationCodeError: If the code doesn't match
            ActivationCodeExpiredError: If the code has expired

        Decision: Once activated, we set activation_code to None to prevent reuse
        and clearly indicate the activation state.
        """
        if self.is_activated:
            raise UserAlreadyActivatedError(self.email)

        if self.activation_code is None:
            raise UserAlreadyActivatedError(self.email)

        # Verify the code (will raise exceptions if invalid or expired)
        self.activation_code.verify(provided_code)

        # Mark as activated
        self.is_activated = True
        self.activated_at = datetime.now(UTC)
        self.activation_code = None  # Clear the code after successful activation

    def regenerate_activation_code(self, expires_in_seconds: int = 60) -> ActivationCode:
        """
        Generate a new activation code.

        Useful if the user didn't receive the email or the code expired.

        Args:
            expires_in_seconds: How long the new code should be valid

        Returns:
            The new activation code

        Raises:
            UserAlreadyActivatedError: If the user is already activated
        """
        if self.is_activated:
            raise UserAlreadyActivatedError(self.email)

        self.activation_code = ActivationCode.generate(expires_in_seconds)
        return self.activation_code

    def __eq__(self, other: object) -> bool:
        """
        Compare users by their ID.

        In DDD, entities are equal if they have the same identity.
        """
        if not isinstance(other, User):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on ID for use in sets and dicts."""
        return hash(self.id)
