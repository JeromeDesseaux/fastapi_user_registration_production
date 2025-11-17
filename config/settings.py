"""
Application configuration settings.

Centralized configuration using Pydantic Settings for type safety and validation.

Decision: Using pydantic-settings for:
1. Type-safe configuration
2. Environment variable loading
3. Validation
4. Default values
5. Easy testing with different configs
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "user-registration-api"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    # Database
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "user_registration"
    database_user: str = "postgres"
    database_password: str = "postgres"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    celery_task_serializer: str = "json"
    celery_result_serializer: str = "json"
    celery_accept_content: list[str] = ["json"]
    celery_timezone: str = "Europe/Paris"
    celery_enable_utc: bool = True
    celery_task_acks_late: bool = True
    celery_task_reject_on_worker_lost: bool = True
    celery_worker_prefetch_multiplier: int = 4
    celery_worker_max_tasks_per_child: int = 1000
    celery_result_expires: int = 3600

    # Security
    secret_key: str = "change-this-in-production"
    activation_code_expiry_seconds: int = 60

    # Email Service (SMTP)
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@dailymotion.com"
    smtp_use_tls: bool = False

    # Feature Flags
    enable_metrics: bool = True
    enable_rate_limiting: bool = True

    # Rate Limiting Configuration
    rate_limit_registration_per_hour: int = 5
    rate_limit_activation_per_minute: int = 3
    rate_limit_global_per_minute: int = 1000


# Global settings instance
settings = Settings()
