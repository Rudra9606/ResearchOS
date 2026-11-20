from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError

from app.db.session import get_db
from app.crud.user import get_user_by_email, create_user
from app.schemas.user import UserCreate
from app.schemas.auth import AuthResponse, RefreshRequest, TokenResponse
from app.models.user import User
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user."""
    try:
        existing_user = get_user_by_email(db, user_data.email)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Please try again shortly.",
        )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered."
        )

    hashed_password = hash_password(user_data.password)

    try:
        user = create_user(
            db=db,
            user_data=user_data,
            password_hash=hashed_password
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered."
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Please try again shortly.",
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return AuthResponse(
        message="Registration successful.",
        user={
            "id": str(user.id),
            "name": user.name,
            "email": user.email
        },
        token=TokenResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=refresh_token,
        )
    )


@router.post("/login", response_model=AuthResponse)
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Authenticate a user and generate a JWT token."""
    try:
        user = get_user_by_email(db, form_data.username)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Please try again shortly.",
        )

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not verify_password(
        form_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return AuthResponse(
        message="Login successful.",
        user={
            "id": str(user.id),
            "name": user.name,
            "email": user.email
        },
        token=TokenResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=refresh_token,
        )
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    request: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Rotate a refresh token and issue a short-lived access token."""

    from uuid import UUID
    import jwt

    try:
        payload = decode_refresh_token(request.refresh_token)
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(user_id),
        token_type="bearer",
        refresh_token=create_refresh_token(user_id),
    )