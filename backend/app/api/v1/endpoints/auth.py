from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.crud.user import get_user_by_email, create_user
from app.schemas.user import UserCreate
from app.schemas.auth import AuthResponse, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token


router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user."""

    existing_user = get_user_by_email(db, user_data.email)

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

    access_token = create_access_token(user.id)

    return AuthResponse(
        message="Registration successful.",
        user={
            "id": str(user.id),
            "name": user.name,
            "email": user.email
        },
        token=TokenResponse(
            access_token=access_token,
            token_type="bearer"
        )
    )


@router.post("/login", response_model=AuthResponse)
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Authenticate a user and generate a JWT token."""

    user = get_user_by_email(db, form_data.username)

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

    return AuthResponse(
        message="Login successful.",
        user={
            "id": str(user.id),
            "name": user.name,
            "email": user.email
        },
        token=TokenResponse(
            access_token=access_token,
            token_type="bearer"
        )
    )