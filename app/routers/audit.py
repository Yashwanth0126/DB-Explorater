from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import get_current_user

router = APIRouter(prefix="/audit", tags=["audit & notifications"])


@router.get("/logs", response_model=list[schemas.AuditLogOut])
def get_audit_logs(limit: int = 100, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/notifications", response_model=list[schemas.NotificationOut])
def get_notifications(database_id: str | None = None, limit: int = 100, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    query = db.query(models.Notification)
    if database_id:
        query = query.filter(models.Notification.database_id == database_id)
    return query.order_by(models.Notification.created_at.desc()).limit(limit).all()
