import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, engine, SessionLocal
from app import models
from app.security import hash_password
from app.scheduler import start_scheduler, stop_scheduler

from app.routers import auth, policies, databases, applications, stakeholders, rotation, dashboard, audit, secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


def _run_lightweight_migrations():
    """
    Adds columns introduced after the DB file already existed (role-based access
    control) without wiping data. Safe to run every startup - it only ALTERs
    tables when a column is actually missing. Works for SQLite and Postgres.
    """
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    with engine.begin() as conn:
        if "users" in existing_tables:
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            if "role" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'user' NOT NULL"))
                logger.info("Migration: added users.role")

        if "target_databases" in existing_tables:
            db_cols = {c["name"] for c in inspector.get_columns("target_databases")}
            if "owner_id" not in db_cols:
                conn.execute(text("ALTER TABLE target_databases ADD COLUMN owner_id VARCHAR"))
                logger.info("Migration: added target_databases.owner_id")


def _ensure_admin_user():
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.username == settings.admin_username).first()
        if not existing:
            admin = models.User(
                username=settings.admin_username,
                email=settings.admin_email,
                hashed_password=hash_password(settings.admin_password),
                role=models.UserRole.admin.value,
            )
            db.add(admin)
            db.commit()
            logger.info("Created default admin user '%s'", settings.admin_username)
        elif existing.role != models.UserRole.admin.value:
            # Make sure the configured bootstrap admin always has admin rights,
            # even if it was created before roles existed.
            existing.role = models.UserRole.admin.value
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()
    _ensure_admin_user()
    start_scheduler()
    logger.info("Startup complete. Environment: %s | DB: %s", settings.env,
                "sqlite" if settings.database_url.startswith("sqlite") else "postgresql")
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Wide-open CORS for hackathon/dev; tighten this once the frontend origin is known.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(policies.router)
app.include_router(databases.router)
app.include_router(applications.router)
app.include_router(stakeholders.router)
app.include_router(rotation.router)
app.include_router(dashboard.router)
app.include_router(audit.router)
app.include_router(secrets.router)


@app.get("/")
def root():
    return {"service": settings.app_name, "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}