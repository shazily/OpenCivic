"""SMTP email delivery when configured."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class EmailService:
    """Send transactional email via SMTP. No-op when SMTP is not configured."""

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.SMTP_HOST.strip())

    @staticmethod
    def send_sync(*, to: str, subject: str, body_html: str) -> dict[str, str]:
        """Deliver email synchronously. Raises when SMTP is configured but delivery fails."""
        if not EmailService.is_configured():
            logger.info("email_skipped_smtp_not_configured", to=to, subject=subject)
            return {"status": "skipped", "reason": "smtp_not_configured"}

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM
        message["To"] = to
        message.set_content("OpenCivic notification. View this message in HTML.")
        message.add_alternative(body_html, subtype="html")

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
            if settings.SMTP_TLS:
                smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)

        logger.info("email_sent", to=to, subject=subject)
        return {"status": "sent"}
