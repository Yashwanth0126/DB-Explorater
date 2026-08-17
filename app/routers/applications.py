from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import get_current_user, is_admin
from app.services import audit_logger
from app.routers.databases import _assert_can_access

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=schemas.ApplicationOut)
def create_application(payload: schemas.ApplicationCreate, db: Session = Depends(get_db),
                        user: models.User = Depends(get_current_user)):
    database = db.query(models.TargetDatabase).filter(models.TargetDatabase.id == payload.database_id).first()
    if not database:
        raise HTTPException(404, "Target database not found")
    _assert_can_access(database, user)

    app_ = models.Application(**payload.model_dump())
    db.add(app_)
    db.commit()
    db.refresh(app_)
    audit_logger.log_action(db, user.username, "create_application", "application", app_.id)
    return app_


@router.get("", response_model=list[schemas.ApplicationOut])
def list_applications(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    query = db.query(models.Application)
    if not is_admin(user):
        query = query.join(models.TargetDatabase).filter(models.TargetDatabase.owner_id == user.id)
    return query.all()


@router.get("/{application_id}", response_model=schemas.ApplicationOut)
def get_application(application_id: str, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    app_ = db.query(models.Application).filter(models.Application.id == application_id).first()
    if not app_:
        raise HTTPException(404, "Application not found")
    _assert_can_access(app_.database, user)
    return app_


@router.delete("/{application_id}")
def delete_application(application_id: str, db: Session = Depends(get_db),
                        user: models.User = Depends(get_current_user)):
    app_ = db.query(models.Application).filter(models.Application.id == application_id).first()
    if not app_:
        raise HTTPException(404, "Application not found")
    _assert_can_access(app_.database, user)
    db.delete(app_)
    db.commit()
    audit_logger.log_action(db, user.username, "delete_application", "application", application_id)
    return {"detail": "deleted"}