"""Authentication Service - handles registration, login, password verification, token generation."""

from uuid import UUID
from datetime import timedelta

from sqlalchemy.orm import Session

from app.crud.user import create_user, get_user_by_email, get_user_by_id
from app.schemas.user import UserCreate, UserResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User


def register_user(
    db: Session,
    user_data: UserCreate,
) -> tuple[User, str]:
    """Register a new user and return the user and access token."""
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise ValueError("Email is already registered.")

    hashed_password = hash_password(user_data.password)
    user = create_user(
        db=db,
        user_data=user_data,
        password_hash=hashed_password,
    )

    access_token = create_access_token(user.id)
    return user, access_token


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> tuple[User, str] | None:
    """Authenticate a user and return the user and access token."""
    user = get_user_by_email(db, email)
    if not user or not user.password_hash:
        return None

    if not verify_password(password, user.password_hash):
        return None

    access_token = create_access_token(user.id)
    return user, access_token


def get_user_profile(
    db: Session,
    user_id: UUID,
) -> User | None:
    """Get user profile by ID."""
    return get_user_by_id(db, user_id)