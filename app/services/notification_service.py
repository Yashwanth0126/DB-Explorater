import logging
import smtplib
from email.mime.text import MIMEText
from typing import List

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app import models

logger = logging.getLogger("notifications")

RESEND_API_URL = "https://api.resend.com/emails"


def _send_via_resend(recipients: List[str], subject: str, body: str) -> bool:
    if not settings.resend_api_key:
        logger.error("RESEND_API_KEY is not set; cannot send notification: %s", subject)
        return False

    payload = {
        "from": f"{settings.notification_from_name} <{settings.notification_from_email}>",
        "to": recipients,
        "subject": subject,
        "text": body,
    }
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(RESEND_API_URL, json=payload, headers=headers, timeout=15)
        if response.status_code >= 400:
            logger.error(
                "Resend API returned an error (%s): %s", response.status_code, response.text
            )
            return False
        return True
    except Exception as exc:
        logger.error("Failed to send notification email via Resend: %s", exc)
        return False


def _send_via_smtp(recipients: List[str], subject: str, body: str) -> bool:
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        logger.error(
            "SMTP is not fully configured (SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD); "
            "cannot send notification: %s", subject,
        )
        return False

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = f"{settings.notification_from_name} <{settings.notification_from_email}>"
    msg["To"] = ", ".join(recipients)

    try:
        if settings.smtp_use_tls:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(settings.smtp_username, settings.smtp_password)
                server.sendmail(settings.notification_from_email, recipients, msg.as_string())
        else:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.login(settings.smtp_username, settings.smtp_password)
                server.sendmail(settings.notification_from_email, recipients, msg.as_string())
        return True
    except Exception as exc:
        logger.error("Failed to send notification email via SMTP: %s", exc)
        return False


def _send_email(recipients: List[str], subject: str, body: str) -> bool:
    if not settings.notifications_enabled:
        logger.info("[notifications disabled] To: %s | %s\n%s", recipients, subject, body)
        return True  # treated as "handled", just not actually emailed

    if not recipients:
        logger.warning("No recipients provided for notification: %s", subject)
        return False

    provider = settings.email_provider.lower()
    if provider == "smtp":
        return _send_via_smtp(recipients, subject, body)
    if provider == "resend":
        return _send_via_resend(recipients, subject, body)

    logger.error("Unknown EMAIL_PROVIDER %r; expected 'resend' or 'smtp'", settings.email_provider)
    return False


def notify(db: Session, database: models.TargetDatabase, notification_type: str,
           subject: str, message: str) -> models.Notification:
    recipients = [s.email for s in database.stakeholders]
    success = _send_email(recipients, subject, message)

    record = models.Notification(
        database_id=database.id,
        notification_type=notification_type,
        subject=subject,
        message=message,
        recipients=",".join(recipients),
        success=success,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def notify_expiry_warning(db: Session, database: models.TargetDatabase, days_remaining: int, auto_rotate: bool):
    subject = f"[Credential Expiry] {database.name} expires in {days_remaining} day(s)"
    body = (
        f"Database: {database.name}\n"
        f"Target user: {database.target_username}\n"
        f"Days remaining: {days_remaining}\n\n"
        f"Automatic rotation is {'enabled' if auto_rotate else 'DISABLED'} for this database.\n"
        + ("The password will be rotated automatically." if auto_rotate
           else "Manual rotation is required — please rotate this credential soon.")
    )
    return notify(db, database, "expiry_warning", subject, body)


def notify_rotation_success(db: Session, database: models.TargetDatabase, new_expiry):
    subject = f"[Rotation Success] {database.name} credential rotated"
    body = (
        f"Database: {database.name}\n"
        f"Target user: {database.target_username}\n"
        f"New expiry: {new_expiry}\n\n"
        f"The password was rotated automatically and propagated to the secret store."
    )
    return notify(db, database, "rotation_success", subject, body)


def notify_rotation_failed(db: Session, database: models.TargetDatabase, error: str):
    subject = f"[ACTION REQUIRED] Rotation FAILED for {database.name}"
    body = (
        f"Database: {database.name}\n"
        f"Target user: {database.target_username}\n\n"
        f"Automatic rotation failed with error:\n{error}\n\n"
        f"Manual intervention is required."
    )
    return notify(db, database, "rotation_failed", subject, body)