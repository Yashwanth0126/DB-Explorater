import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app import models
from app.services import rule_engine

logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler()


def check_all_credentials():
    """Runs the rule engine against every active database. This is the job APScheduler fires."""
    db = SessionLocal()
    try:
        databases = db.query(models.TargetDatabase).filter(models.TargetDatabase.is_active == True).all()  # noqa: E712
        logger.info("Scheduler tick: evaluating %d database(s)", len(databases))
        for database in databases:
            try:
                result = rule_engine.evaluate_database(db, database, triggered_by="scheduler")
                logger.info("Database %s -> %s", database.name, result)
            except Exception as exc:
                # Individual database failures should never kill the whole scheduler run
                logger.error("Scheduler failed evaluating database %s: %s", database.name, exc)
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        check_all_credentials,
        "interval",
        minutes=settings.scheduler_interval_minutes,
        id="credential_expiry_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started, running every %d minute(s)", settings.scheduler_interval_minutes)


def stop_scheduler():
    scheduler.shutdown(wait=False)
