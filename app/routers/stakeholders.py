from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import get_current_user
from app.services import audit_logger

router = APIRouter(prefix="/stakeholders", tags=["stakeholders"])


@router.post("", response_model=schemas.StakeholderOut)
def create_stakeholder(payload: schemas.StakeholderCreate, db: Session = Depends(get_db),
                        user: models.User = Depends(get_current_user)):
    database = db.query(models.TargetDatabase).filter(models.TargetDatabase.id == payload.database_id).first()
    if not database:
        raise HTTPException(404, "Target database not found")

    stakeholder = models.Stakeholder(**payload.model_dump())
    db.add(stakeholder)
    db.commit()
    db.refresh(stakeholder)
    audit_logger.log_action(db, user.username, "create_stakeholder", "stakeholder", stakeholder.id)
    return stakeholder


@router.get("", response_model=list[schemas.StakeholderOut])
def list_stakeholders(database_id: str | None = None, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    query = db.query(models.Stakeholder)
    if database_id:
        query = query.filter(models.Stakeholder.database_id == database_id)
    return query.all()


@router.delete("/{stakeholder_id}")
def delete_stakeholder(stakeholder_id: str, db: Session = Depends(get_db),
                        user: models.User = Depends(get_current_user)):
    stakeholder = db.query(models.Stakeholder).filter(models.Stakeholder.id == stakeholder_id).first()
    if not stakeholder:
        raise HTTPException(404, "Stakeholder not found")
    db.delete(stakeholder)
    db.commit()
    audit_logger.log_action(db, user.username, "delete_stakeholder", "stakeholder", stakeholder_id)
    return {"detail": "deleted"}
