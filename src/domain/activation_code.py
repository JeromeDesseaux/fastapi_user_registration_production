"""
ActivationCode value object.

Represents a 4-digit activation code with expiry logic.
This is a value object in DDD terms - immutable and defined by its attributes.
"""

import random
from datetime import UTC, datetime, timedelta

from src.domain.exceptions import ActivationCodeExpiredError, InvalidActivationCodeError


class ActivationCode:
    """
    Value object representing a 4-digit activation code.

    The code expires after a configurable duration (default: 60 seconds as per requirements).
    This class encapsulates the business logic for code generation, validation, and expiry.
    """

    CODE_LENGTH = 4
    CODE_MIN = 1000
    CODE_MAX = 9999

    def __init__(
        self,
        code: str,
        created_at: datetime,
        expires_in_seconds: int = 60,
    ):
        """
        Initialize an ActivationCode.

        Args:
            code: The 4-digit code as a string
            created_at: When the code was created
            expires_in_seconds: How long the code is valid (default: 60 seconds)

        Raises:
            InvalidActivationCodeError: If the code format is invalid
        """
        if not self._is_valid_format(code):
            raise InvalidActivationCodeError()

        self._code = code
        self._created_at = created_at
        self._expires_at = created_at + timedelta(seconds=expires_in_seconds)

    @staticmethod
    def _is_valid_format(code: str) -> bool:
        """
        Validate the format of an activation code.

        Args:
            code: The code to validate

        Returns:
            True if the code is a 4-digit string, False otherwise
        """
        return (
            code.isdigit()
            and len(code) == ActivationCode.CODE_LENGTH
            and ActivationCode.CODE_MIN <= int(code) <= ActivationCode.CODE_MAX
        )

    @classmethod
    def generate(cls, expires_in_seconds: int = 60) -> "ActivationCode":
        """
        Generate a new random 4-digit activation code.

        Args:
            expires_in_seconds: How long the code should be valid (default: 60 seconds)

        Returns:
            A new ActivationCode instance with a random code

        Decision: Using random.randint for code generation. In production, consider
        using secrets.randbelow for cryptographically secure random numbers.
        For this use case (temporary 60-second codes), random.randint is acceptable.
        """
        code = str(random.randint(cls.CODE_MIN, cls.CODE_MAX))
        return cls(
            code=code,
            created_at=datetime.now(UTC),
            expires_in_seconds=expires_in_seconds,
        )

    def verify(self, provided_code: str, current_time: datetime | None = None) -> None:
        """
        Verify if the provided code matches and is not expired.

        Args:
            provided_code: The code to verify
            current_time: The current time (default: now, allows testing with specific times)

        Raises:
            InvalidActivationCodeError: If the code doesn't match
            ActivationCodeExpiredError: If the code has expired
        """
        if not self._is_valid_format(provided_code):
            raise InvalidActivationCodeError()

        if provided_code != self._code:
            raise InvalidActivationCodeError()

        check_time = current_time or datetime.now(UTC)
        if self.is_expired(check_time):
            raise ActivationCodeExpiredError()

    def is_expired(self, current_time: datetime | None = None) -> bool:
        """
        Check if the activation code has expired.

        Args:
            current_time: The time to check against (default: now)

        Returns:
            True if expired, False otherwise
        """
        check_time = current_time or datetime.now(UTC)
        return check_time >= self._expires_at

    @property
    def code(self) -> str:
        """Get the activation code value."""
        return self._code

    @property
    def created_at(self) -> datetime:
        """Get when the code was created."""
        return self._created_at

    @property
    def expires_at(self) -> datetime:
        """Get when the code expires."""
        return self._expires_at

    def __str__(self) -> str:
        """String representation of the activation code."""
        return self._code

    def __eq__(self, other: object) -> bool:
        """
        Compare two activation codes for equality.

        Value objects are equal if their values are equal.
        """
        if not isinstance(other, ActivationCode):
            return False
        return self._code == other._code and self._created_at == other._created_at
