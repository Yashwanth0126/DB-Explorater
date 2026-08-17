from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import get_current_user
from app.services import rule_engine
from app.services.rotation_engine import RotationError
from app.routers.databases import _assert_can_access

router = APIRouter(prefix="/rotation", tags=["rotation"])


@router.post("/{database_id}/rotate-now", response_model=schemas.RotationHistoryOut)
def rotate_now(database_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Manually trigger an immediate rotation, bypassing the days-remaining threshold."""
    database = db.query(models.TargetDatabase).filter(models.TargetDatabase.id == database_id).first()
    if not database:
        raise HTTPException(404, "Database not found")
    _assert_can_access(database, user)

    validity_days = database.rotation_policy.rotation_interval_days if database.rotation_policy else 30

    try:
        rule_engine.rotate_database(db, database, validity_days=validity_days,
                                     triggered_by=f"manual:{user.username}")
    except RotationError as exc:
        raise HTTPException(502, f"Rotation failed: {exc}")

    latest = (
        db.query(models.RotationHistory)
        .filter(models.RotationHistory.database_id == database_id)
        .order_by(models.RotationHistory.created_at.desc())
        .first()
    )
    return latest


@router.post("/{database_id}/evaluate")
def evaluate_now(database_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Runs the same rule the scheduler uses (notify/rotate based on days remaining), on demand."""
    database = db.query(models.TargetDatabase).filter(models.TargetDatabase.id == database_id).first()
    if not database:
        raise HTTPException(404, "Database not found")
    _assert_can_access(database, user)
    try:
        return rule_engine.evaluate_database(db, database, triggered_by=f"manual:{user.username}")
    except RotationError as exc:
        # Rotation was attempted (threshold was breached) and failed. The failure was
        # already recorded to rotation history / notifications / audit log by rule_engine;
        # this just gives the caller a clean response instead of a raw 500.
        return {"action": "rotation_failed", "error": str(exc)}


@router.get("/{database_id}/history", response_model=list[schemas.RotationHistoryOut])
def get_history(database_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    database = db.query(models.TargetDatabase).filter(models.TargetDatabase.id == database_id).first()
    if not database:
        raise HTTPException(404, "Database not found")
    _assert_can_access(database, user)
    return (
        db.query(models.RotationHistory)
        .filter(models.RotationHistory.database_id == database_id)
        .order_by(models.RotationHistory.created_at.desc())
        .all()
    )