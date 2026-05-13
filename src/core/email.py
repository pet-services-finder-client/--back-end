"""Email sending via Resend.

We use Resend as our transactional email provider. This module wraps the
Resend SDK so the rest of the codebase doesn't need to know which provider
we use — if we ever switch to Sendgrid/Mailgun/SES, only this file changes.
"""
import logging

import resend

from src.core.config import settings


logger = logging.getLogger(__name__)

# Configure Resend SDK once on module import
resend.api_key = settings.RESEND_API_KEY


def send_email(
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
) -> str | None:
    """Send a transactional email via Resend.

    Args:
        to: Recipient email address
        subject: Email subject line
        html: HTML body of the email
        text: Optional plain-text fallback for clients that don't render HTML

    Returns:
        Resend message ID on success, None on failure.
        We don't raise on failure to avoid blocking user-facing actions
        (e.g. if the email service is down, a password reset request can
        still complete from the user's perspective — they just won't get
        the email; logs will show the issue).
    """
    params: dict = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text is not None:
        params["text"] = text

    try:
        response = resend.Emails.send(params)
        message_id = response.get("id")
        logger.info("Email sent to %s (subject=%r, id=%s)", to, subject, message_id)
        return message_id
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc, exc_info=True)
        return None
