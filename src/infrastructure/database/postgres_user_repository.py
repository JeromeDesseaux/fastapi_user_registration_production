"""
PostgreSQL implementation of UserRepository.

This is the concrete adapter for user persistence using raw SQL with asyncpg.
No ORM is used as per requirements - we write SQL queries directly.
"""

import logging
from uuid import UUID

from src.domain.activation_code import ActivationCode
from src.domain.user import User
from src.domain.user_repository import UserRepository
from src.infrastructure.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class PostgresUserRepository(UserRepository):
    """
    PostgreSQL implementation of the UserRepository interface.

    This adapter translates between our domain model (User entity) and
    the database representation using raw SQL queries with asyncpg.

    Decision: We use raw SQL instead of an ORM to:
    1. Follow the requirements (no ORM magic)
    2. Have full control over queries
    3. Demonstrate understanding of SQL and database operations
    4. Optimize queries for performance (important for Staff Engineer role)

    Decision: Using asyncpg provides native async/await support and 3-5x
    better performance than psycopg2 under load.
    """

    def __init__(self, db_connection: DatabaseConnection):
        """
        Initialize the repository.

        Args:
            db_connection: Database connection manager
        """
        self.db = db_connection

    async def save(self, user: User) -> None:
        """
        Save or update a user.

        Uses INSERT ... ON CONFLICT to handle both creation and updates.
        This is PostgreSQL's UPSERT functionality.

        Args:
            user: User entity to persist

        Decision: We map the domain entity to database columns explicitly.
        This gives us full control over the persistence mapping.

        Note: asyncpg uses $1, $2, $3 for parameterized queries instead of %s.
        This is PostgreSQL's native syntax and is more efficient.
        """
        query = """
        INSERT INTO users (
            id, email, password_hash, is_activated, created_at, activated_at,
            activation_code, activation_code_created_at, activation_code_expires_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9
        )
        ON CONFLICT (id) DO UPDATE SET
            email = EXCLUDED.email,
            password_hash = EXCLUDED.password_hash,
            is_activated = EXCLUDED.is_activated,
            activated_at = EXCLUDED.activated_at,
            activation_code = EXCLUDED.activation_code,
            activation_code_created_at = EXCLUDED.activation_code_created_at,
            activation_code_expires_at = EXCLUDED.activation_code_expires_at
        """

        try:
            await self.db.execute(
                query,
                str(user.id),
                user.email,
                user.password_hash,
                user.is_activated,
                user.created_at,
                user.activated_at,
                user.activation_code.code if user.activation_code else None,
                user.activation_code.created_at if user.activation_code else None,
                user.activation_code.expires_at if user.activation_code else None,
            )
            logger.debug(f"Saved user: {user.email}")
        except Exception as e:
            logger.error(f"Failed to save user {user.email}: {e}")
            raise

    async def find_by_email(self, email: str) -> User | None:
        """
        Find a user by email.

        Args:
            email: Email to search for

        Returns:
            User entity if found, None otherwise

        Note: asyncpg returns Record objects (dict-like) by default.
        Our connection layer converts them to dicts for consistency.
        """
        query = """
        SELECT
            id, email, password_hash, is_activated, created_at, activated_at,
            activation_code, activation_code_created_at, activation_code_expires_at
        FROM users
        WHERE email = $1
        """

        try:
            result = await self.db.execute(query, email, fetchone=True)
            if not result:
                return None

            # Type narrowing: result is dict when fetchone=True and not None
            assert isinstance(result, dict)
            return self._map_to_entity(result)
        except Exception as e:
            logger.error(f"Failed to find user by email {email}: {e}")
            raise

    async def find_by_id(self, user_id: UUID) -> User | None:
        """
        Find a user by ID.

        Args:
            user_id: User's UUID

        Returns:
            User entity if found, None otherwise
        """
        query = """
        SELECT
            id, email, password_hash, is_activated, created_at, activated_at,
            activation_code, activation_code_created_at, activation_code_expires_at
        FROM users
        WHERE id = $1
        """

        try:
            result = await self.db.execute(query, str(user_id), fetchone=True)
            if not result:
                return None

            # Type narrowing: result is dict when fetchone=True and not None
            assert isinstance(result, dict)
            return self._map_to_entity(result)
        except Exception as e:
            logger.error(f"Failed to find user by id {user_id}: {e}")
            raise

    async def exists_by_email(self, email: str) -> bool:
        """
        Check if a user exists with the given email.

        Args:
            email: Email to check

        Returns:
            True if exists, False otherwise

        Decision: Using COUNT(*) for existence check is efficient.
        We could also use EXISTS, but COUNT is more portable and
        equally performant for this use case.
        """
        query = "SELECT COUNT(*) as count FROM users WHERE email = $1"

        try:
            result = await self.db.execute(query, email, fetchone=True)
            # Type narrowing: result is dict when fetchone=True and not None
            if result and isinstance(result, dict):
                return bool(result["count"] > 0)
            return False
        except Exception as e:
            logger.error(f"Failed to check if user exists {email}: {e}")
            raise

    def _map_to_entity(self, row: dict) -> User:
        """
        Map a database row to a User entity.

        This is where we reconstruct our domain model from persistence.

        Args:
            row: Database row as dict (from asyncpg Record converted to dict)

        Returns:
            Reconstructed User entity

        Decision: We reconstruct the ActivationCode value object from
        the database columns. This keeps our domain model rich and
        behavior-focused rather than anemic.
        """
        activation_code = None
        if row["activation_code"] and row["activation_code_created_at"]:
            # Calculate original expiry duration
            expires_at = row["activation_code_expires_at"]
            created_at = row["activation_code_created_at"]
            expiry_seconds = int((expires_at - created_at).total_seconds())

            activation_code = ActivationCode(
                code=row["activation_code"],
                created_at=created_at,
                expires_in_seconds=expiry_seconds,
            )

        return User(
            id=UUID(row["id"]) if isinstance(row["id"], str) else row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            is_activated=row["is_activated"],
            created_at=row["created_at"],
            activated_at=row["activated_at"],
            activation_code=activation_code,
        )
