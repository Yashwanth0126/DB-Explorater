from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import get_current_user
from app.crypto import encrypt_value
from app.services import secret_manager, audit_logger

router = APIRouter(prefix="/databases", tags=["target databases"])


def _compute_status(database: models.TargetDatabase, db: Session) -> schemas.TargetDatabaseStatusOut:
    credential = secret_manager.get_active_credential(db, database.id)
    remaining = secret_manager.days_remaining(credential)

    last_failed = (
        db.query(models.RotationHistory)
        .filter(models.RotationHistory.database_id == database.id)
        .order_by(models.RotationHistory.created_at.desc())
        .first()
    )

    notify_before = database.rotation_policy.notify_before_days if database.rotation_policy else 7

    if remaining is None:
        status_str = "unknown"
    elif last_failed and last_failed.status == models.RotationStatus.failed and remaining <= notify_before:
        status_str = "rotation_failed"
    elif remaining < 0:
        status_str = "expired"
    elif remaining <= notify_before:
        status_str = "expiring_soon"
    else:
        status_str = "healthy"

    out = schemas.TargetDatabaseStatusOut.model_validate(database)
    out.current_expiry = credential.expires_at if credential else None
    out.days_remaining = remaining
    out.status = status_str
    return out


@router.post("", response_model=schemas.TargetDatabaseOut)
def create_database(payload: schemas.TargetDatabaseCreate, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    data = payload.model_dump()
    plain_target_password = data.pop("target_password")
    initial_expiry_days = data.pop("initial_expiry_days")
    data["admin_password_encrypted"] = encrypt_value(data.pop("admin_password"))

    database = models.TargetDatabase(**data)
    db.add(database)
    db.commit()
    db.refresh(database)

    # Record the credential that's already set on the target DB (not rotated yet,
    # just brought under management) so day-count tracking starts immediately.
    secret_manager.store_new_credential(db, database, plain_target_password, initial_expiry_days)

    audit_logger.log_action(db, user.username, "create_database", "database", database.id)
    return database


@router.get("", response_model=list[schemas.TargetDatabaseStatusOut])
def list_databases(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    databases = db.query(models.TargetDatabase).all()
    return [_compute_status(d, db) for d in databases]


@router.get("/{database_id}", response_model=schemas.TargetDatabaseStatusOut)
def get_database(database_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    database = db.query(models.TargetDatabase).filter(models.TargetDatabase.id == database_id).first()
    if not database:
        raise HTTPException(404, "Database not found")
    return _compute_status(database, db)


@router.delete("/{database_id}")
def delete_database(database_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    database = db.query(models.TargetDatabase).filter(models.TargetDatabase.id == database_id).first()
    if not database:
        raise HTTPException(404, "Database not found")
    db.delete(database)
    db.commit()
    audit_logger.log_action(db, user.username, "delete_database", "database", database_id)
    return {"detail": "deleted"}
