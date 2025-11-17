"""
Domain-specific exceptions.

These exceptions represent business rule violations and domain errors.
They are independent of infrastructure concerns.
"""


class DomainError(Exception):
    """Base exception for all domain errors."""

    pass


class UserAlreadyExistsError(DomainError):
    """Raised when attempting to create a user with an email that already exists."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"User with email '{email}' already exists")


class UserNotFoundError(DomainError):
    """Raised when a user cannot be found."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"User with email '{email}' not found")


class UserAlreadyActivatedError(DomainError):
    """Raised when attempting to activate an already activated user."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"User with email '{email}' is already activated")


class InvalidActivationCodeError(DomainError):
    """Raised when the provided activation code is invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid activation code provided")


class ActivationCodeExpiredError(DomainError):
    """Raised when the activation code has expired."""

    def __init__(self) -> None:
        super().__init__("Activation code has expired")


class InvalidEmailError(DomainError):
    """Raised when an email format is invalid."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Invalid email format: '{email}'")


class WeakPasswordError(DomainError):
    """Raised when a password doesn't meet security requirements."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Password does not meet requirements: {reason}")
