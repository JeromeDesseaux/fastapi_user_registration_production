"""
SMTP Email Service implementation.

This is a production-ready implementation that sends emails via SMTP.
For local development, we use Mailhog (SMTP testing server with web UI).

Decision: This demonstrates modeling email as a third-party service as per requirements.
The architecture remains clean - this adapter can be swapped with any other
email service (SendGrid HTTP API, AWS SES, etc.) without changing domain logic.
"""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader

from src.application.email_service import EmailService

logger = logging.getLogger(__name__)


class SmtpEmailService(EmailService):
    """
    Email service that sends emails via SMTP.

    In production, this would connect to:
    - Mailgun SMTP (smtp.mailgun.org:587)
    - SendGrid SMTP (smtp.sendgrid.net:587)
    - AWS SES SMTP (email-smtp.region.amazonaws.com:587)

    For local development, we use Mailhog:
    - SMTP server on port 1025
    - Web UI at http://localhost:8025

    Decision: Using SMTP instead of HTTP API for simplicity, but the
    architecture allows easy swap to HTTP-based services.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        from_email: str = "noreply@dailymotion.com",
    ):
        """
        Initialize the SMTP email service.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: SMTP authentication username (optional for Mailhog)
            smtp_password: SMTP authentication password (optional for Mailhog)
            from_email: Sender email address

        Decision: Credentials are optional to support both:
        - Mailhog (no auth needed for local testing)
        - Production SMTP servers (auth required)
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email

        # Set up Jinja2 template environment
        # Decision: Using Jinja2 for email templates provides:
        # - Separation of concerns (content vs sending logic)
        # - Easy customization by non-developers
        # - Template inheritance and reusability
        templates_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=True,  # Prevent XSS in HTML emails
        )

        logger.info(
            f"SMTP Email Service initialized: {smtp_host}:{smtp_port} "
            f"(auth: {'yes' if smtp_username else 'no'})"
        )

    async def send_activation_code(self, email: str, code: str) -> None:
        """
        Send activation code to user's email via SMTP.

        This method:
        1. Creates a MIME email with HTML content
        2. Connects to SMTP server
        3. Authenticates if credentials provided
        4. Sends the email
        5. Handles errors and retries (via Celery)

        Args:
            email: Recipient email
            code: 4-digit activation code

        Raises:
            SMTPException: If email sending fails (will trigger Celery retry)

        Decision: We use HTML emails for better UX, but include plain text
        fallback for email clients that don't support HTML.
        """
        # Create email message
        message = MIMEMultipart("alternative")
        message["Subject"] = "Activate Your Dailymotion Account"
        message["From"] = self.from_email
        message["To"] = email

        # Render templates with context
        # Decision: Using Jinja2 templates for email content provides:
        # - Separation of content from sending logic
        # - Easy updates by non-developers (marketing team)
        # - Consistency across emails
        # - Template variables for dynamic content
        context = {"code": code, "expiry_seconds": 60}

        text_template = self.jinja_env.get_template("activation_code.txt")
        html_template = self.jinja_env.get_template("activation_code.html")

        text_content = text_template.render(context)
        html_content = html_template.render(context)

        # Attach both versions (plain text fallback + HTML)
        message.attach(MIMEText(text_content, "plain", _charset="utf-8"))
        message.attach(MIMEText(html_content, "html", _charset="utf-8"))

        # Send via SMTP
        try:
            logger.info(f"Sending activation code to {email} via SMTP")

            # Connect to SMTP server
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                timeout=10.0,
            ) as smtp:
                # Authenticate if credentials provided (not needed for Mailhog)
                if self.smtp_username and self.smtp_password:
                    await smtp.login(self.smtp_username, self.smtp_password)

                # Send email
                await smtp.send_message(message)

            logger.info(f"✓ Email sent successfully to {email}")

        except Exception as e:
            logger.error(f"Failed to send email to {email}: {e}")
            raise EmailServiceError(f"Failed to send activation email: {e}") from e


class EmailServiceError(Exception):
    """Raised when email sending fails."""

    pass
