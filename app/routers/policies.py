from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import get_current_user
from app.services import audit_logger

router = APIRouter(prefix="/policies", tags=["rotation policies"])


@router.post("", response_model=schemas.RotationPolicyOut)
def create_policy(payload: schemas.RotationPolicyCreate, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    policy = models.RotationPolicy(**payload.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    audit_logger.log_action(db, user.username, "create_policy", "rotation_policy", policy.id)
    return policy


@router.get("", response_model=list[schemas.RotationPolicyOut])
def list_policies(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.RotationPolicy).all()


@router.get("/{policy_id}", response_model=schemas.RotationPolicyOut)
def get_policy(policy_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    policy = db.query(models.RotationPolicy).filter(models.RotationPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(404, "Policy not found")
    return policy


@router.delete("/{policy_id}")
def delete_policy(policy_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    policy = db.query(models.RotationPolicy).filter(models.RotationPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(404, "Policy not found")
    db.delete(policy)
    db.commit()
    audit_logger.log_action(db, user.username, "delete_policy", "rotation_policy", policy_id)
    return {"detail": "deleted"}
