from pydantic import BaseModel


# JWT token response
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


# JWT token payload
class TokenData(BaseModel):
    user_id: str | None = None


# Authentication response
class AuthResponse(BaseModel):
    message: str
    user: dict
    token: TokenResponse