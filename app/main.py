import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine, SessionLocal
from app import models
from app.security import hash_password
from app.scheduler import start_scheduler, stop_scheduler

from app.routers import auth, policies, databases, applications, stakeholders, rotation, dashboard, audit, secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


def _ensure_admin_user():
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.username == settings.admin_username).first()
        if not existing:
            admin = models.User(
                username=settings.admin_username,
                email=settings.admin_email,
                hashed_password=hash_password(settings.admin_password),
            )
            db.add(admin)
            db.commit()
            logger.info("Created default admin user '%s'", settings.admin_username)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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
