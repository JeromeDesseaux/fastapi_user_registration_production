"""
Email service interface (Port).

Defines the contract for sending emails.
The infrastructure layer will provide the adapter implementation.
"""

from abc import ABC, abstractmethod


class EmailService(ABC):
    """
    Abstract interface for email sending.

    This is a "port" in Hexagonal Architecture.
    The infrastructure layer provides the concrete adapter.

    Decision: We model this as an HTTP API call to a third-party service,
    as specified in the requirements. The implementation will handle
    the HTTP communication, but the domain/application layers only
    know about this abstract interface.
    """

    @abstractmethod
    async def send_activation_code(self, email: str, code: str) -> None:
        """
        Send an activation code to a user's email.

        This represents a call to a third-party email service HTTP API.

        Args:
            email: Recipient's email address
            code: The 4-digit activation code to send

        Raises:
            EmailServiceError: If sending fails

        Note: The actual implementation might:
        - Make an HTTP POST request to an external service
        - Print to console for development/testing
        - Use a local SMTP server
        """
        pass
