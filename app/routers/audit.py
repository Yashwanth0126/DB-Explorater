from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import get_current_user, is_admin
from app.routers.databases import _assert_can_access

router = APIRouter(prefix="/audit", tags=["audit & notifications"])


@router.get("/logs", response_model=list[schemas.AuditLogOut])
def get_audit_logs(limit: int = 100, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    query = db.query(models.AuditLog)
    if not is_admin(user):
        # Non-admins only ever see actions they themselves performed.
        query = query.filter(models.AuditLog.actor == user.username)
    return query.order_by(models.AuditLog.created_at.desc()).limit(limit).all()


@router.get("/notifications", response_model=list[schemas.NotificationOut])
def get_notifications(database_id: str | None = None, limit: int = 100, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    query = db.query(models.Notification)
    if database_id:
        database = db.query(models.TargetDatabase).filter(models.TargetDatabase.id == database_id).first()
        if not database:
            raise HTTPException(404, "Target database not found")
        _assert_can_access(database, user)
        query = query.filter(models.Notification.database_id == database_id)
    elif not is_admin(user):
        query = query.join(
            models.TargetDatabase, models.Notification.database_id == models.TargetDatabase.id
        ).filter(models.TargetDatabase.owner_id == user.id)
    return query.order_by(models.Notification.created_at.desc()).limit(limit).all()