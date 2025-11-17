"""
Mailhog API client for E2E testing.

Mailhog provides an HTTP API to retrieve and inspect emails sent during tests.
This client wraps the API and provides convenient methods for E2E tests.

API Documentation: https://github.com/mailhog/MailHog/blob/master/docs/APIv2.md
"""

import base64
import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MailhogClient:
    """
    Client for interacting with Mailhog HTTP API.

    Mailhog is an SMTP testing server that captures emails and provides
    an HTTP API to retrieve them. This is perfect for E2E tests.

    Decision: We use httpx (same as integration tests) for HTTP requests.
    """

    def __init__(self, base_url: str = "http://mailhog:8025"):
        """
        Initialize Mailhog client.

        Args:
            base_url: Base URL of Mailhog HTTP API (default: http://mailhog:8025)

        Decision: Default to Docker service name "mailhog" for consistency
        with integration tests.
        """
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=10.0)

    def get_all_messages(self) -> list[dict[str, Any]]:
        """
        Get all messages from Mailhog.

        Returns:
            List of email message objects

        Raises:
            httpx.HTTPError: If request fails
        """
        response = self.client.get("/api/v2/messages")
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])

    def get_messages_for(self, to_email: str) -> list[dict[str, Any]]:
        """
        Get all messages sent to a specific email address.

        Args:
            to_email: Email address to filter by

        Returns:
            List of matching email message objects
        """
        all_messages = self.get_all_messages()
        matching_messages = []

        for msg in all_messages:
            # Check To recipients
            to_recipients = msg.get("To", [])
            for recipient in to_recipients:
                # Reconstruct email from Mailbox@Domain
                mailbox = recipient.get("Mailbox", "")
                domain = recipient.get("Domain", "")
                recipient_email = f"{mailbox}@{domain}"

                if to_email.lower() == recipient_email.lower():
                    matching_messages.append(msg)
                    break

        return matching_messages

    def wait_for_email(
        self, to_email: str, timeout: int = 10, poll_interval: float = 0.5
    ) -> dict[str, Any]:
        """
        Wait for an email to arrive at Mailhog.

        Polls the Mailhog API until an email is found or timeout is reached.

        Args:
            to_email: Email address to wait for
            timeout: Maximum time to wait in seconds (default: 10)
            poll_interval: How often to poll in seconds (default: 0.5)

        Returns:
            The email message object

        Raises:
            TimeoutError: If no email arrives within timeout

        Decision: Polling with exponential backoff would be better for production,
        but fixed interval is simpler and adequate for tests.
        """
        start_time = time.time()
        attempt = 0

        while time.time() - start_time < timeout:
            attempt += 1
            messages = self.get_messages_for(to_email)

            if messages:
                logger.info(f"[MAILHOG] Email found for {to_email} after {attempt} attempts")
                return messages[0]  # Return most recent

            time.sleep(poll_interval)

        raise TimeoutError(
            f"No email received for {to_email} within {timeout} seconds ({attempt} attempts)"
        )

    def extract_activation_code(self, message: dict[str, Any]) -> str:
        """
        Extract the 4-digit activation code from an email message.

        Args:
            message: Email message object from Mailhog API

        Returns:
            The 4-digit activation code

        Raises:
            ValueError: If no activation code is found

        Decision: We search both HTML and plain text parts for the code.
        The regex looks for a 4-digit number, assuming our email template
        formats it prominently.

        We also handle base64-encoded content, which occurs when emails
        are sent with charset="utf-8" (Python's email library automatically
        applies base64 encoding for UTF-8 content).
        """
        # Get email content (try both HTML and plain text)
        content = message.get("Content", {})
        body_html = content.get("Body", "")

        # Also check MIME parts for multipart messages
        mime_parts = message.get("MIME", {}).get("Parts", [])

        all_content = body_html
        for part in mime_parts:
            part_body = part.get("Body", "")

            # Check if content is base64-encoded
            headers = part.get("Headers", {})
            content_transfer_encoding = headers.get("Content-Transfer-Encoding", [])

            # Decode base64 content if needed
            if content_transfer_encoding and "base64" in content_transfer_encoding[0]:
                try:
                    decoded_body = base64.b64decode(part_body).decode("utf-8")
                    all_content += " " + decoded_body
                except Exception as e:
                    logger.warning(f"[MAILHOG] Failed to decode base64 content: {e}")
                    all_content += " " + part_body
            else:
                all_content += " " + part_body

        # Look for 4-digit code
        # Decision: Use word boundaries to avoid matching year or other numbers
        match = re.search(r"\b(\d{4})\b", all_content)

        if not match:
            raise ValueError(
                f"No 4-digit activation code found in email. Content preview: {all_content[:200]}..."
            )

        code = match.group(1)
        logger.info(f"[MAILHOG] Extracted activation code: {code}")
        return code

    def clear_all_messages(self) -> None:
        """
        Delete all messages from Mailhog.

        Used for cleanup between test scenarios.

        Raises:
            httpx.HTTPError: If request fails
        """
        response = self.client.delete("/api/v1/messages")
        response.raise_for_status()
        logger.info("[MAILHOG] All messages cleared")

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()
