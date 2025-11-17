"""
Celery configuration and application setup.

Celery is used for asynchronous task processing, specifically for sending
activation emails. This allows us to:
1. Return API responses quickly without waiting for email sending
2. Retry failed email sends automatically
3. Handle email service outages gracefully
4. Scale email processing independently

Decision: Using centralized configuration from config.settings.
All Celery settings are loaded from environment variables via pydantic-settings.
"""

import logging

from celery import Celery
from config.settings import settings

logger = logging.getLogger(__name__)

# Create Celery application
# Decision: We use a single Celery app instance for the entire application
# Configuration comes from centralized settings loaded from .env
celery_app = Celery(
    "user_registration_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration
# Decision: All configuration is centralized in config/settings.py
# This provides type safety, validation, and easier testing
celery_app.conf.update(
    # Task settings
    task_serializer=settings.celery_task_serializer,
    accept_content=settings.celery_accept_content,
    result_serializer=settings.celery_result_serializer,
    timezone=settings.celery_timezone,
    enable_utc=settings.celery_enable_utc,
    # Retry configuration
    # Decision: We retry failed email sends with exponential backoff
    # This handles temporary network issues or email service downtime
    task_acks_late=settings.celery_task_acks_late,  # Acknowledge task only after completion
    task_reject_on_worker_lost=settings.celery_task_reject_on_worker_lost,  # Retry if worker crashes
    # Performance settings
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,  # Number of tasks to prefetch per worker
    worker_max_tasks_per_child=settings.celery_worker_max_tasks_per_child,  # Restart worker after N tasks (memory management)
    # Result backend settings
    result_expires=settings.celery_result_expires,  # Results expire after 1 hour
)

# Auto-discover tasks in all packages under src.infrastructure.tasks
# Decision: Using autodiscover_tasks() to automatically find all tasks.py files
# in subdirectories (email/, notifications/, etc.). This scales well as we add
# more task modules without needing to manually import each one.
celery_app.autodiscover_tasks(["src.infrastructure.tasks.email"])

logger.info("Celery application configured")
