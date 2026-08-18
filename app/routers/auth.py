from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import verify_password, hash_password, create_access_token, get_current_user, require_admin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(models.User)
        .filter(
            (models.User.username == payload.username)
            | (models.User.email == payload.email)
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is already registered",
        )

    user = models.User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=models.UserRole.user.value,  # public signup is always a regular user
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Sign the user straight in after registering, same as login does.
    token = create_access_token(subject=user.username, role=user.role)
    return schemas.Token(access_token=token)


@router.get("/me", response_model=schemas.UserOut)
def get_me(user: models.User = Depends(get_current_user)):
    return user


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    """Admin-only: list every user in the system."""
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@router.post("/users", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: schemas.AdminUserCreate, db: Session = Depends(get_db),
                 admin: models.User = Depends(require_admin)):
    """
    Admin-only: directly create an account with a chosen role (admin or user),
    e.g. inviting someone straight in as an admin. Unlike /auth/signup, this
    skips the "sign up as user, then get promoted" flow entirely.
    """
    if payload.role not in (models.UserRole.admin.value, models.UserRole.user.value):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "role must be 'admin' or 'user'")

    existing = (
        db.query(models.User)
        .filter(
            (models.User.username == payload.username)
            | (models.User.email == payload.email)
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is already registered",
        )

    user = models.User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/role", response_model=schemas.UserOut)
def update_user_role(user_id: str, payload: schemas.UserRoleUpdate, db: Session = Depends(get_db),
                      admin: models.User = Depends(require_admin)):
    """Admin-only: promote/demote a user between 'admin' and 'user'."""
    if payload.role not in (models.UserRole.admin.value, models.UserRole.user.value):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "role must be 'admin' or 'user'")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    target.role = payload.role
    db.commit()
    db.refresh(target)
    return target


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user.username, role=user.role)
    return schemas.Token(access_token=token)