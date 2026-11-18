from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from pwdlib import PasswordHash

from app.core.config import settings


# Password hashing configuration
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Generate a secure password hash."""

    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """Verify a password against its stored hash."""

    return password_hash.verify(
        plain_password,
        hashed_password
    )


def create_access_token(
    user_id: UUID,
    expires_delta: timedelta | None = None
) -> str:
    """Generate a JWT access token."""

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire
    }

    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return token


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""

    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
    )