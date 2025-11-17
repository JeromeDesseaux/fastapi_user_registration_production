"""
Email-related Celery tasks.

These tasks run asynchronously in Celery workers, separate from the API process.
This provides resilience, scalability, and better user experience.

Decision: Organized in a dedicated 'email' package under tasks/. This allows us to:
1. Scale to multiple task domains (email/, notifications/, reports/, etc.)
2. Each domain has its own tasks.py file (Celery convention)
3. Use autodiscover_tasks() to automatically register all task modules
4. Keep related tasks organized and maintainable
"""

import asyncio
import logging
from typing import Any

from config.settings import settings

from src.infrastructure.email.smtp_email_service import SmtpEmailService
from src.infrastructure.tasks.celery_config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def send_activation_email_task(self: Any, email: str, code: str) -> str:
    """
    Celery task to send activation email.

    This task runs in a Celery worker process and handles:
    - Sending the email via the email service
    - Automatic retries on failure with exponential backoff
    - Error logging and tracking

    Args:
        self: Celery task instance (from bind=True)
        email: Recipient email address
        code: 4-digit activation code

    Returns:
        Status message

    Retry Configuration:
    - autoretry_for: Automatically retry on any Exception
    - retry_backoff: Use exponential backoff (2^retry_num seconds)
    - retry_backoff_max: Maximum backoff time (10 minutes)
    - retry_jitter: Add randomness to prevent thundering herd
    - max_retries: Maximum 3 retry attempts

    Decision: We use aggressive retry logic because:
    1. Email delivery is important for user activation
    2. Temporary failures (network issues, service downtime) are common
    3. We want to maximize delivery success rate
    4. Failed emails should be visible in Celery monitoring

    Example retry timeline:
    - Attempt 1: Immediate
    - Attempt 2: ~2 seconds later
    - Attempt 3: ~4 seconds later
    - Attempt 4: ~8 seconds later
    """
    try:
        logger.info(f"[CELERY] Sending activation email to {email} (Task: {self.request.id})")

        # Create email service instance with SMTP configuration from centralized settings
        # Decision: We create a new instance per task rather than using a
        # global instance to avoid potential issues with connection pooling
        # and ensure each task is independent
        email_service = SmtpEmailService(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password,
            from_email=settings.smtp_from_email,
        )

        # Send email (async operation)
        # We use asyncio.run() to execute the async method in the sync Celery task
        asyncio.run(email_service.send_activation_code(email, code))

        logger.info(f"[CELERY] Email sent successfully to {email}")
        return f"Email sent to {email}"

    except Exception as e:
        # Log the error before retry
        logger.error(
            f"[CELERY] Failed to send email to {email} "
            f"(Attempt {self.request.retries + 1}/{self.max_retries}): {e}"
        )
        # Re-raise to trigger retry
        raise


class CeleryTaskQueue:
    """
    Adapter for enqueueing Celery tasks.

    This class provides the TaskQueue protocol implementation for Celery,
    allowing the application layer to remain independent of Celery details.
    """

    @staticmethod
    def enqueue_send_activation_email(email: str, code: str) -> str:
        """
        Enqueue a task to send activation email.

        Args:
            email: Recipient email
            code: Activation code

        Returns:
            Task ID for tracking

        Decision: We use delay() instead of apply_async() for simplicity.
        For more control (e.g., countdown, eta, expires), we'd use apply_async().
        """
        task = send_activation_email_task.delay(email, code)
        logger.info(f"[CELERY] Enqueued email task {task.id} for {email}")
        return str(task.id)
