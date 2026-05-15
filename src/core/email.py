"""Email sending via Resend.

We use Resend as our transactional email provider. This module wraps the
Resend SDK so the rest of the codebase doesn't need to know which provider
we use — if we ever switch to Sendgrid/Mailgun/SES, only this file changes.
"""
import logging

import resend

from src.core.config import settings
from src.core.i18n import to_vocative


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


def send_password_reset_email(
    to: str,
    reset_url: str,
    user_name: str | None = None,
) -> str | None:
    """Send a password reset email with a clickable reset link.

    Args:
        to: recipient email
        reset_url: full URL the user clicks to reset (e.g. https://app/reset?token=xyz)
        user_name: user's full name (used in greeting; falls back to generic greeting)
    """
    greeting = f"Привіт, {to_vocative(user_name)}!" if user_name else "Привіт!"

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #1f2937;">
      <h1 style="color: #111827;">🐾 Pawly — Відновлення пароля</h1>
      <p>{greeting}</p>
      <p>
        Ми отримали запит на відновлення пароля для вашого акаунта Pawly.
        Щоб створити новий пароль і знову отримати доступ до платформи,
        перейдіть за посиланням нижче:
      </p>
      <p style="margin: 32px 0;">
        <a href="{reset_url}"
           style="background-color: #2563eb; color: white; padding: 12px 24px;
                  text-decoration: none; border-radius: 6px; display: inline-block;">
          Відновити пароль
        </a>
      </p>
      <p style="color: #6b7280; font-size: 14px;">
        Або скопіюйте це посилання у браузер:<br>
        <a href="{reset_url}" style="color: #2563eb; word-break: break-all;">{reset_url}</a>
      </p>
      <p style="color: #6b7280; font-size: 14px;">
        Посилання дійсне <strong>1 годину</strong>. Якщо це були не ви —
        просто проігноруйте цей лист. Ваш акаунт залишиться у безпеці.
      </p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
      <p style="color: #9ca3af; font-size: 12px;">Дякуємо, що користуєтесь Pawly! 🐾<br>— Команда Pawly</p>
    </body>
    </html>
    """

    text = f"""
{greeting}

Ми отримали запит на відновлення пароля для вашого акаунта Pawly.
Щоб створити новий пароль, перейдіть за посиланням:

{reset_url}

Посилання дійсне 1 годину. Якщо це були не ви — просто проігноруйте
цей лист. Ваш акаунт залишиться у безпеці.

Дякуємо, що користуєтесь Pawly!
— Команда Pawly
    """.strip()

    return send_email(
        to=to,
        subject="Pawly: Відновлення пароля",
        html=html,
        text=text,
    )

def send_welcome_email(
    to: str,
    user_name: str | None = None,
) -> str | None:
    """Send a welcome email to a newly registered user.

    Args:
        to: recipient email
        user_name: user's full name (used in greeting; falls back to generic greeting)
    """
    greeting = f"Привіт, {to_vocative(user_name)}!" if user_name else "Привіт!"

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #1f2937;">
      <h1 style="color: #111827;">🐾 Ласкаво просимо до Pawly!</h1>
      <p>{greeting}</p>
      <p>
        Ми раді вітати вас у <strong>Pawly</strong> — платформі для власників
        домашніх тварин у Києві та області.
      </p>
      <p>
        Тепер ви зможете швидко знаходити ветеринарні клініки, зоомагазини,
        грумінг-салони та інші pet services поруч із вами.
      </p>
      <p style="margin: 32px 0;">
        <a href="{settings.FRONTEND_URL}"
           style="background-color: #2563eb; color: white; padding: 12px 24px;
                  text-decoration: none; border-radius: 6px; display: inline-block;">
          Перейти до Pawly
        </a>
      </p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
      <p style="color: #9ca3af; font-size: 12px;">
        Дякуємо, що обрали Pawly! 🐾<br>— Команда Pawly
      </p>
    </body>
    </html>
    """

    text = f"""
{greeting}

Ми раді вітати вас у Pawly — платформі для власників домашніх тварин
у Києві та області.

Тепер ви зможете швидко знаходити ветеринарні клініки, зоомагазини,
грумінг-салони та інші pet services поруч із вами.

Перейти до Pawly: {settings.FRONTEND_URL}

Дякуємо, що обрали Pawly!
— Команда Pawly
    """.strip()

    return send_email(
        to=to,
        subject="Ласкаво просимо до Pawly! 🐾",
        html=html,
        text=text,
    )
