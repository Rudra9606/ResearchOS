from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def create_user(
    db: Session,
    user_data: UserCreate,
    password_hash: str
) -> User:
    """Create a new user."""

    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=password_hash
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception:
        db.rollback()
        raise


def get_user_by_id(db: Session, user_id: UUID):
    """Retrieve a user by ID."""

    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str):
    """Retrieve a user by email."""

    statement = select(User).where(User.email == email)
    return db.scalar(statement)


def get_all_users(
    db: Session,
    skip: int = 0,
    limit: int = 100
):
    """Retrieve users with pagination."""

    statement = select(User).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


def update_user(
    db: Session,
    user_id: UUID,
    user_data: UserUpdate
):
    """Update user information."""

    user = get_user_by_id(db, user_id)

    if user is None:
        return None

    update_data = user_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise


def delete_user(db: Session, user_id: UUID) -> bool:
    """Delete a user."""

    user = get_user_by_id(db, user_id)

    if user is None:
        return False

    try:
        db.delete(user)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise