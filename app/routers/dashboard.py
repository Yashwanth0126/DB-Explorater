from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import get_current_user
from app.services import secret_manager
from app.routers.databases import _compute_status

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=schemas.DashboardSummary)
def summary(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    databases = db.query(models.TargetDatabase).all()
    counts = {"healthy": 0, "expiring_soon": 0, "expired": 0, "rotation_failed": 0}
    for database in databases:
        row = _compute_status(database, db)
        if row.status in counts:
            counts[row.status] += 1
    return schemas.DashboardSummary(total_databases=len(databases), **counts)


@router.get("/table", response_model=list[schemas.DashboardRow])
def table(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    databases = db.query(models.TargetDatabase).all()
    rows = []
    for database in databases:
        status_row = _compute_status(database, db)
        rows.append(schemas.DashboardRow(
            database_id=database.id,
            database_name=database.name,
            application_names=[a.name for a in database.applications],
            days_remaining=status_row.days_remaining,
            status=status_row.status,
            auto_rotation=database.rotation_policy.auto_rotate if database.rotation_policy else True,
        ))
    return rows
