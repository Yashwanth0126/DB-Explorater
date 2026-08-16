from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import models
from app.crypto import encrypt_value, decrypt_value


def get_active_credential(db: Session, database_id: str) -> models.Credential | None:
    return (
        db.query(models.Credential)
        .filter(models.Credential.database_id == database_id, models.Credential.is_active == True)  # noqa: E712
        .order_by(models.Credential.created_at.desc())
        .first()
    )


def store_new_credential(db: Session, database: models.TargetDatabase, plain_password: str,
                          validity_days: int) -> models.Credential:
    """Deactivates the previous credential and stores the new one, encrypted at rest."""
    old = get_active_credential(db, database.id)
    if old:
        old.is_active = False
        db.add(old)

    new_cred = models.Credential(
        database_id=database.id,
        encrypted_password=encrypt_value(plain_password),
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(days=validity_days),
    )
    db.add(new_cred)
    db.commit()
    db.refresh(new_cred)
    return new_cred


def get_plain_password(credential: models.Credential) -> str:
    return decrypt_value(credential.encrypted_password)


def days_remaining(credential: models.Credential | None) -> int | None:
    if credential is None:
        return None
    delta = credential.expires_at - datetime.utcnow()
    return delta.days
