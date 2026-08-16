from sqlalchemy.orm import Session
from app import models


def log_action(db: Session, actor: str, action: str, entity_type: str = None,
                entity_id: str = None, details: str = None):
    entry = models.AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(entry)
    db.commit()
    return entry
