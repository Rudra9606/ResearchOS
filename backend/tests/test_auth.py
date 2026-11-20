"""Authentication tests for ResearchOS backend (Task 3.11)."""

import pytest
from datetime import timedelta

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


class TestPasswordHashing:
    """Test password hashing with Argon2."""

    def test_hash_password(self):
        """Test that passwords are hashed correctly."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "TestPassword123!"
        wrong_password = "WrongPassword123!"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False


class TestJWTToken:
    """Test JWT generation and validation."""

    def test_create_access_token(self):
        """Test JWT token creation."""
        import uuid
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self):
        """Test JWT token decoding."""
        import uuid
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_invalid_token(self):
        """Test decoding an invalid token."""
        import jwt
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token("invalid.token.string")

    def test_decode_expired_token(self):
        import uuid
        import jwt

        token = create_access_token(uuid.uuid4(), expires_delta=timedelta(seconds=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_refresh_token_is_distinct_from_access_token(self):
        import uuid
        import jwt
        user_id = uuid.uuid4()
        refresh_token = create_refresh_token(user_id)
        payload = decode_refresh_token(refresh_token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(refresh_token)

    def test_decode_token_with_invalid_subject(self):
        import jwt
        from app.core.config import settings

        token = jwt.encode(
            {"sub": "not-a-uuid"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        from app.core.dependencies import get_current_user
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=token, db=None)
        assert exc_info.value.status_code == 401


class TestUserRegistration:
    """Test user registration."""

    def test_register_user_success(self, client, test_user_data):
        """Test successful user registration."""
        # Use unique email to avoid conflicts with auth_headers fixture
        import time
        unique_data = dict(test_user_data)
        unique_data["email"] = f"unique_{int(time.time()*1000)}@example.com"
        response = client.post("/api/v1/auth/register", json=unique_data)
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Registration successful."
        assert data["user"]["email"] == unique_data["email"]
        assert data["user"]["name"] == unique_data["name"]
        assert "password" not in str(data)
        assert "token" in data
        assert data["token"]["access_token"] is not None

    def test_register_duplicate_email(self, client, test_user_data):
        """Test duplicate email rejection."""
        import time
        unique_data = dict(test_user_data)
        unique_data["email"] = f"dup_{int(time.time()*1000)}@example.com"
        # Register first user
        client.post("/api/v1/auth/register", json=unique_data)

        # Try to register with same email
        response = client.post("/api/v1/auth/register", json=unique_data)
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    def test_password_not_in_response(self, client, test_user_data):
        """Ensure passwords are never returned in API responses."""
        import time
        unique_data = dict(test_user_data)
        unique_data["email"] = f"nopw_{int(time.time()*1000)}@example.com"
        response = client.post("/api/v1/auth/register", json=unique_data)
        data = response.json()
        response_str = str(data)
        assert "password" not in response_str.lower()
        assert "password_hash" not in response_str.lower()


class TestUserLogin:
    """Test user login functionality."""

    def test_login_success(self, client, test_user_data):
        """Test successful user login."""
        import time
        unique_data = dict(test_user_data)
        unique_data["email"] = f"login_{int(time.time()*1000)}@example.com"
        client.post("/api/v1/auth/register", json=unique_data)
        response = client.post(
            "/api/v1/auth/login",
            data={"username": unique_data["email"], "password": unique_data["password"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Login successful."
        assert data["token"]["access_token"] is not None

    def test_login_incorrect_password(self, client, test_user_data):
        """Test incorrect password rejection."""
        import time
        unique_data = dict(test_user_data)
        unique_data["email"] = f"wrongpw_{int(time.time()*1000)}@example.com"
        client.post("/api/v1/auth/register", json=unique_data)
        response = client.post(
            "/api/v1/auth/login",
            data={"username": unique_data["email"], "password": "WrongPassword123!"}
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent@example.com", "password": "password123"}
        )
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Test protected endpoints with JWT authentication."""

    def test_protected_endpoint_with_token(self, client, auth_headers):
        """Test accessing protected endpoint with valid token."""
        response = client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 200

    def test_protected_endpoint_without_token(self, client):
        """Test accessing protected endpoint without token."""
        response = client.get("/api/v1/users/")
        assert response.status_code == 401

    def test_protected_endpoint_with_invalid_token(self, client):
        """Test accessing protected endpoint with invalid token."""
        headers = {"Authorization": "Bearer invalid.token.string"}
        response = client.get("/api/v1/users/", headers=headers)
        assert response.status_code == 401


class TestCrossUserAccess:
    """Test that users cannot access another user's resources."""

    def test_cannot_access_other_user_project(self, client, auth_headers, test_user_data):
        """Test that user cannot access another user's project."""
        user2_data = {
            "name": "User Two",
            "email": "user2@example.com",
            "password": "TestPassword123!",
        }
        client.post("/api/v1/auth/register", json=user2_data)
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": user2_data["email"], "password": user2_data["password"]}
        )
        user2_token = login_resp.json()["token"]["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}
        response = client.get("/api/v1/projects/", headers=user2_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["projects"] == []