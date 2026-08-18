from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict


# ---------- Auth ----------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class AdminUserCreate(BaseModel):
    """Used by admins to directly create an account with a chosen role
    (e.g. inviting someone straight in as an admin), skipping public signup."""
    username: str
    email: EmailStr
    password: str
    role: str = "user"  # "admin" | "user"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    email: str
    role: str
    created_at: datetime


class UserRoleUpdate(BaseModel):
    role: str  # "admin" | "user"

# ---------- Rotation Policy ----------

class RotationPolicyCreate(BaseModel):
    name: str
    rotation_interval_days: int = 30
    notify_before_days: int = 7
    auto_rotate: bool = True


class RotationPolicyOut(RotationPolicyCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


# ---------- Target Database ----------

class TargetDatabaseCreate(BaseModel):
    name: str
    db_type: str = "postgresql"
    host: str
    port: int = 5432
    db_name: str
    admin_username: str
    admin_password: str          # plaintext in request, encrypted before storage
    target_username: str
    target_password: str         # initial password for target_username, encrypted before storage
    rotation_policy_id: Optional[str] = None
    initial_expiry_days: int = 30


class TargetDatabaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    db_type: str
    host: str
    port: int
    db_name: str
    admin_username: str
    target_username: str
    rotation_policy_id: Optional[str]
    owner_id: Optional[str] = None
    is_active: bool
    created_at: datetime


class TargetDatabaseStatusOut(TargetDatabaseOut):
    current_expiry: Optional[datetime] = None
    days_remaining: Optional[int] = None
    status: str = "unknown"  # healthy | expiring_soon | expired | rotation_failed


# ---------- Application ----------

class ApplicationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    database_id: str
    webhook_url: Optional[str] = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: Optional[str]
    database_id: str
    api_key: str
    webhook_url: Optional[str]
    created_at: datetime


# ---------- Stakeholder ----------

class StakeholderCreate(BaseModel):
    database_id: str
    name: str
    email: EmailStr


class StakeholderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    database_id: str
    name: str
    email: str


# ---------- Rotation History ----------

class RotationHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    database_id: str
    status: str
    old_expiry: Optional[datetime]
    new_expiry: Optional[datetime]
    message: Optional[str]
    triggered_by: str
    created_at: datetime


# ---------- Notification ----------

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    database_id: Optional[str]
    notification_type: str
    subject: str
    message: str
    recipients: Optional[str]
    success: bool
    created_at: datetime


# ---------- Audit ----------

class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor: str
    action: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    details: Optional[str]
    created_at: datetime


# ---------- Dashboard ----------

class DashboardSummary(BaseModel):
    total_databases: int
    healthy: int
    expiring_soon: int
    expired: int
    rotation_failed: int


class DashboardRow(BaseModel):
    database_id: str
    database_name: str
    application_names: List[str]
    days_remaining: Optional[int]
    status: str
    auto_rotation: bool


# ---------- Secret Manager (application-facing) ----------

class SecretOut(BaseModel):
    database_id: str
    database_name: str
    host: str
    port: int
    db_name: str
    username: str
    password: str
    expires_at: datetime