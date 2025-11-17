"""
Unit tests for ActivationCode value object.

Tests the business logic for code generation, validation, and expiry.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.activation_code import ActivationCode
from src.domain.exceptions import ActivationCodeExpiredError, InvalidActivationCodeError


class TestActivationCodeGeneration:
    """Test activation code generation."""

    def test_generate_creates_valid_code(self) -> None:
        """Test that generate() creates a valid 4-digit code."""
        code = ActivationCode.generate()

        assert len(code.code) == 4
        assert code.code.isdigit()
        assert 1000 <= int(code.code) <= 9999

    def test_generate_sets_created_at(self) -> None:
        """Test that created_at is set to current time."""
        before = datetime.now(UTC)
        code = ActivationCode.generate()
        after = datetime.now(UTC)

        assert before <= code.created_at <= after

    def test_generate_sets_expiry(self) -> None:
        """Test that expiry is set correctly."""
        code = ActivationCode.generate(expires_in_seconds=60)
        expected_expiry = code.created_at + timedelta(seconds=60)

        assert code.expires_at == expected_expiry


class TestActivationCodeValidation:
    """Test activation code validation logic."""

    def test_verify_with_correct_code_succeeds(self) -> None:
        """Test that verify succeeds with the correct code."""
        code = ActivationCode.generate()

        # Should not raise
        code.verify(code.code)

    def test_verify_with_incorrect_code_raises_error(self) -> None:
        """Test that verify raises error with wrong code."""
        code = ActivationCode("1234", datetime.now(UTC))

        with pytest.raises(InvalidActivationCodeError):
            code.verify("5678")

    def test_verify_with_invalid_format_raises_error(self) -> None:
        """Test that verify raises error with invalid format."""
        code = ActivationCode.generate()

        with pytest.raises(InvalidActivationCodeError):
            code.verify("abc")

        with pytest.raises(InvalidActivationCodeError):
            code.verify("12345")

        with pytest.raises(InvalidActivationCodeError):
            code.verify("123")

    def test_verify_with_expired_code_raises_error(self) -> None:
        """Test that verify raises error if code is expired."""
        created_at = datetime.now(UTC) - timedelta(seconds=120)
        code = ActivationCode("1234", created_at, expires_in_seconds=60)

        with pytest.raises(ActivationCodeExpiredError):
            code.verify("1234")

    def test_verify_at_exact_expiry_time_is_expired(self) -> None:
        """Test that code is expired at exactly the expiry time."""
        created_at = datetime.now(UTC)
        code = ActivationCode("1234", created_at, expires_in_seconds=60)
        expiry_time = created_at + timedelta(seconds=60)

        with pytest.raises(ActivationCodeExpiredError):
            code.verify("1234", current_time=expiry_time)


class TestActivationCodeExpiry:
    """Test activation code expiry logic."""

    def test_is_expired_returns_false_when_not_expired(self) -> None:
        """Test that is_expired returns False when code is still valid."""
        code = ActivationCode.generate(expires_in_seconds=60)

        assert not code.is_expired()

    def test_is_expired_returns_true_when_expired(self) -> None:
        """Test that is_expired returns True when code has expired."""
        created_at = datetime.now(UTC) - timedelta(seconds=120)
        code = ActivationCode("1234", created_at, expires_in_seconds=60)

        assert code.is_expired()

    def test_is_expired_with_custom_time(self) -> None:
        """Test is_expired with a custom check time."""
        created_at = datetime.now(UTC)
        code = ActivationCode("1234", created_at, expires_in_seconds=60)

        # Not expired at 30 seconds
        check_time = created_at + timedelta(seconds=30)
        assert not code.is_expired(check_time)

        # Expired at 61 seconds
        check_time = created_at + timedelta(seconds=61)
        assert code.is_expired(check_time)


class TestActivationCodeEquality:
    """Test activation code equality."""

    def test_equal_codes_are_equal(self) -> None:
        """Test that codes with same values are equal."""
        created_at = datetime.now(UTC)
        code1 = ActivationCode("1234", created_at)
        code2 = ActivationCode("1234", created_at)

        assert code1 == code2

    def test_different_codes_are_not_equal(self) -> None:
        """Test that codes with different values are not equal."""
        created_at = datetime.now(UTC)
        code1 = ActivationCode("1234", created_at)
        code2 = ActivationCode("5678", created_at)

        assert code1 != code2

    def test_code_not_equal_to_non_code(self) -> None:
        """Test that code is not equal to non-ActivationCode objects."""
        code = ActivationCode.generate()

        assert code != "1234"
        assert code != 1234
        assert code is not None
