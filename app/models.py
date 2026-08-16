import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class RotationPolicy(Base):
    __tablename__ = "rotation_policies"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    rotation_interval_days = Column(Integer, default=30)   # password validity window
    notify_before_days = Column(Integer, default=7)        # warn threshold
    auto_rotate = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    databases = relationship("TargetDatabase", back_populates="rotation_policy")


class TargetDatabase(Base):
    """A managed database instance whose credential we monitor/rotate."""
    __tablename__ = "target_databases"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    db_type = Column(String, default="postgresql")  # postgresql supported first
    host = Column(String, nullable=False)
    port = Column(Integer, default=5432)
    db_name = Column(String, nullable=False)

    # Superuser/admin credential used ONLY to execute ALTER USER ... PASSWORD
    admin_username = Column(String, nullable=False)
    admin_password_encrypted = Column(Text, nullable=False)

    # The application-facing DB user whose password gets rotated
    target_username = Column(String, nullable=False)

    rotation_policy_id = Column(String, ForeignKey("rotation_policies.id"), nullable=True)
    rotation_policy = relationship("RotationPolicy", back_populates="databases")

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    credentials = relationship("Credential", back_populates="database", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="database", cascade="all, delete-orphan")
    stakeholders = relationship("Stakeholder", back_populates="database", cascade="all, delete-orphan")
    rotation_history = relationship("RotationHistory", back_populates="database", cascade="all, delete-orphan")


class Credential(Base):
    """Current + historical encrypted secret for a target database's rotated user."""
    __tablename__ = "credentials"

    id = Column(String, primary_key=True, default=gen_uuid)
    database_id = Column(String, ForeignKey("target_databases.id"), nullable=False)
    encrypted_password = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    database = relationship("TargetDatabase", back_populates="credentials")


class Application(Base):
    """An application that consumes a rotated credential via the secret manager."""
    __tablename__ = "applications"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    database_id = Column(String, ForeignKey("target_databases.id"), nullable=False)

    # Applications authenticate to GET /secrets/current using this key
    api_key = Column(String, unique=True, default=gen_uuid)

    # Optional: called with POST {database_id, new_expiry} whenever rotation succeeds,
    # so the app can proactively reload its credential instead of polling.
    webhook_url = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    database = relationship("TargetDatabase", back_populates="applications")


class Stakeholder(Base):
    __tablename__ = "stakeholders"

    id = Column(String, primary_key=True, default=gen_uuid)
    database_id = Column(String, ForeignKey("target_databases.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)

    database = relationship("TargetDatabase", back_populates="stakeholders")


class RotationStatus(str, enum.Enum):
    success = "success"
    failed = "failed"


class RotationHistory(Base):
    __tablename__ = "rotation_history"

    id = Column(String, primary_key=True, default=gen_uuid)
    database_id = Column(String, ForeignKey("target_databases.id"), nullable=False)
    status = Column(Enum(RotationStatus), nullable=False)
    old_expiry = Column(DateTime, nullable=True)
    new_expiry = Column(DateTime, nullable=True)
    message = Column(Text, nullable=True)
    triggered_by = Column(String, default="scheduler")  # scheduler | manual:<username>
    created_at = Column(DateTime, default=datetime.utcnow)

    database = relationship("TargetDatabase", back_populates="rotation_history")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=gen_uuid)
    database_id = Column(String, ForeignKey("target_databases.id"), nullable=True)
    notification_type = Column(String, nullable=False)  # expiry_warning | rotation_success | rotation_failed
    subject = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    recipients = Column(Text, nullable=True)  # comma-separated
    success = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    actor = Column(String, nullable=False)       # username or "scheduler"
    action = Column(String, nullable=False)       # e.g. "rotate_credential", "create_database"
    entity_type = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
