from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, ConfigDict


# User registration
class UserCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=100
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=128
    )


# User login
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# User response
class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# User profile update
class UserUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100
    )