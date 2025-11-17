"""
User repository interface (Port).

This interface defines the contract for user persistence.
Following Hexagonal Architecture, the domain defines the interface,
and the infrastructure layer provides the implementation.

This allows the domain to remain independent of persistence details.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.user import User


class UserRepository(ABC):
    """
    Abstract repository interface for User persistence.

    This is a "port" in Hexagonal Architecture terminology.
    The infrastructure layer will provide the concrete "adapter" implementation.
    """

    @abstractmethod
    async def save(self, user: User) -> None:
        """
        Persist a user entity.

        This method handles both creation and updates.

        Args:
            user: The user entity to persist

        Raises:
            Exception: If persistence fails
        """
        pass

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None:
        """
        Find a user by their email address.

        Args:
            email: The email to search for

        Returns:
            The User entity if found, None otherwise

        Raises:
            Exception: If query fails
        """
        pass

    @abstractmethod
    async def find_by_id(self, user_id: UUID) -> User | None:
        """
        Find a user by their ID.

        Args:
            user_id: The user's UUID

        Returns:
            The User entity if found, None otherwise

        Raises:
            Exception: If query fails
        """
        pass

    @abstractmethod
    async def exists_by_email(self, email: str) -> bool:
        """
        Check if a user with the given email exists.

        Args:
            email: The email to check

        Returns:
            True if a user exists, False otherwise

        Raises:
            Exception: If query fails
        """
        pass
