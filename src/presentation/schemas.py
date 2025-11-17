"""
API request/response schemas (DTOs).

These Pydantic models define the API contract for requests and responses.
They provide validation, serialization, and documentation.

Decision: We keep these separate from domain entities to maintain
separation of concerns. The API layer should not expose internal domain details.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterUserRequest(BaseModel):
    """Request schema for user registration."""

    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description="User's password (minimum 8 characters)",
        examples=["SecurePassword123"],
    )


class RegisterUserResponse(BaseModel):
    """Response schema for user registration."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="User's unique identifier")
    email: str = Field(..., description="User's email address")
    is_activated: bool = Field(..., description="Whether the account is activated")
    created_at: datetime = Field(..., description="When the account was created")
    message: str = Field(
        ...,
        description="Success message",
        examples=["User registered successfully. Check your email for the activation code."],
    )


class ActivateUserRequest(BaseModel):
    """Request schema for user activation."""

    activation_code: str = Field(
        ...,
        min_length=4,
        max_length=4,
        pattern=r"^\d{4}$",
        description="4-digit activation code received by email",
        examples=["1234"],
    )


class ActivateUserResponse(BaseModel):
    """Response schema for user activation."""

    email: str = Field(..., description="User's email address")
    is_activated: bool = Field(..., description="Activation status (should be True)")
    activated_at: datetime | None = Field(..., description="When the account was activated")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Account activated successfully"],
    )


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: str | None = Field(None, description="Additional error details")


class HealthCheckResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(..., description="Service status", examples=["healthy"])
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(..., description="Current server time")
