from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import secret_manager

router = APIRouter(prefix="/secrets", tags=["secret manager (application-facing)"])


def _authenticate_application(x_api_key: str, db: Session) -> models.Application:
    app_ = db.query(models.Application).filter(models.Application.api_key == x_api_key).first()
    if not app_:
        raise HTTPException(status_code=401, detail="Invalid application API key")
    return app_


@router.get("/current", response_model=schemas.SecretOut)
def get_current_secret(x_api_key: str = Header(..., description="Application API key"),
                        db: Session = Depends(get_db)):
    """
    Applications call this (instead of hardcoding a DB password) to always get the
    latest rotated credential for the database they're bound to.
    """
    app_ = _authenticate_application(x_api_key, db)
    database = app_.database

    credential = secret_manager.get_active_credential(db, database.id)
    if not credential:
        raise HTTPException(404, "No active credential for this database yet")

    return schemas.SecretOut(
        database_id=database.id,
        database_name=database.name,
        host=database.host,
        port=database.port,
        db_name=database.db_name,
        username=database.target_username,
        password=secret_manager.get_plain_password(credential),
        expires_at=credential.expires_at,
    )
