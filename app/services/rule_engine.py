import logging
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app import models
from app.crypto import encrypt_value
from app.services import secret_manager, notification_service, audit_logger
from app.services.rotation_engine import (
    generate_secure_password, rotate_postgres_password, test_connection, RotationError,
)

logger = logging.getLogger("rule_engine")


def evaluate_database(db: Session, database: models.TargetDatabase, triggered_by: str = "scheduler"):
    """
    Core rule:
        days_remaining > notify_before_days  -> no action
        days_remaining <= notify_before_days -> notify
        auto_rotate enabled                  -> rotate automatically
    """
    policy = database.rotation_policy
    notify_before_days = policy.notify_before_days if policy else 7
    auto_rotate = policy.auto_rotate if policy else True
    validity_days = policy.rotation_interval_days if policy else 30

    credential = secret_manager.get_active_credential(db, database.id)
    remaining = secret_manager.days_remaining(credential)

    if remaining is None:
        # No credential on record yet — nothing to evaluate until one is created.
        return {"action": "none", "reason": "no_active_credential"}

    if remaining > notify_before_days:
        return {"action": "none", "days_remaining": remaining}

    # Threshold reached: notify stakeholders regardless of auto_rotate
    notification_service.notify_expiry_warning(db, database, remaining, auto_rotate)

    if not auto_rotate:
        return {"action": "notified_only", "days_remaining": remaining}

    result = rotate_database(db, database, validity_days=validity_days, triggered_by=triggered_by)
    return {"action": "rotated", "result": result}


def rotate_database(db: Session, database: models.TargetDatabase, validity_days: int = 30,
                     triggered_by: str = "manual") -> dict:
    """
    Full rotation flow:
      generate password -> change it in postgres -> verify connection ->
      store new encrypted credential -> propagate to apps -> notify -> audit log
    On any failure: alert stakeholders + audit log the failure, and re-raise.
    """
    old_credential = secret_manager.get_active_credential(db, database.id)
    old_expiry = old_credential.expires_at if old_credential else None

    new_password = generate_secure_password()

    try:
        rotate_postgres_password(database, new_password)

        if not test_connection(database, database.target_username, new_password):
            raise RotationError("Post-rotation connection test failed")

        new_credential = secret_manager.store_new_credential(db, database, new_password, validity_days)

        # The admin credential used to run ALTER USER must stay in sync with reality.
        # If the admin account IS the target account (common when there's no separate
        # superuser), rotating the target password also changes the admin password —
        # otherwise the next rotation attempt authenticates with a stale password and
        # fails, even though the previous rotation succeeded.
        if database.admin_username == database.target_username:
            database.admin_password_encrypted = encrypt_value(new_password)
            db.add(database)
            db.commit()

        _propagate_to_applications(db, database, new_credential)

        db.add(models.RotationHistory(
            database_id=database.id,
            status=models.RotationStatus.success,
            old_expiry=old_expiry,
            new_expiry=new_credential.expires_at,
            message="Rotation succeeded and application credentials were propagated.",
            triggered_by=triggered_by,
        ))
        db.commit()

        notification_service.notify_rotation_success(db, database, new_credential.expires_at)
        audit_logger.log_action(db, triggered_by, "rotate_credential_success", "database", database.id)

        return {"status": "success", "new_expiry": new_credential.expires_at}

    except Exception as exc:
        db.add(models.RotationHistory(
            database_id=database.id,
            status=models.RotationStatus.failed,
            old_expiry=old_expiry,
            new_expiry=None,
            message=str(exc),
            triggered_by=triggered_by,
        ))
        db.commit()

        notification_service.notify_rotation_failed(db, database, str(exc))
        audit_logger.log_action(db, triggered_by, "rotate_credential_failed", "database", database.id,
                                 details=str(exc))
        raise


def _propagate_to_applications(db: Session, database: models.TargetDatabase, credential: models.Credential):
    """Best-effort webhook ping so applications can proactively reload their credential.
    Applications can also always pull the latest secret via GET /secrets/current."""
    for app in database.applications:
        if not app.webhook_url:
            continue
        try:
            httpx.post(
                app.webhook_url,
                json={
                    "database_id": database.id,
                    "database_name": database.name,
                    "rotated_at": datetime.utcnow().isoformat(),
                    "new_expiry": credential.expires_at.isoformat(),
                },
                timeout=5,
            )
        except Exception as exc:
            # Non-fatal: the app can still pull the new secret from /secrets/current
            logger.warning("Webhook notify failed for app %s: %s", app.name, exc)