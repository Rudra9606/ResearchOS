"""Test configuration and fixtures for ResearchOS backend tests."""

import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from psycopg import connect, sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base
from app.db.session import get_db
from app.core.config import settings
from app.crud.user import create_user
from app.schemas.user import UserCreate
from app.core.security import hash_password

def _temporary_test_database_url() -> tuple[str, str, str]:
    """Create a uniquely named local test database; never reuse a fixed DB."""
    configured_url = os.environ.get("TEST_DATABASE_URL")
    source = "TEST_DATABASE_URL" if configured_url else "DATABASE_URL"
    url = make_url(configured_url or settings.DATABASE_URL)
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise RuntimeError("Tests require a PostgreSQL TEST_DATABASE_URL.")
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Test database creation is restricted to a local PostgreSQL server.")

    source_name = url.database or ""
    if configured_url and not source_name.startswith("researchos_test"):
        raise RuntimeError("TEST_DATABASE_URL must name a researchos_test database.")
    if not configured_url and source_name != "researchos":
        raise RuntimeError(
            "Set TEST_DATABASE_URL to a local researchos_test database URL; "
            "the configured application database is not the expected development database."
        )

    database_name = f"researchos_pytest_{uuid4().hex}"
    admin_url = url.set(database="postgres", drivername="postgresql")
    connection_string = admin_url.render_as_string(hide_password=False)
    with connect(connection_string, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    test_url = url.set(database=database_name).render_as_string(hide_password=False)
    return test_url, connection_string, database_name


@pytest.fixture(scope="session")
def test_engine():
    """Use an isolated database that this fixture creates and removes."""
    test_url, admin_url, database_name = _temporary_test_database_url()
    engine = create_engine(test_url)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()"
                ),
                (database_name,),
            )
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(database_name)
                )
            )


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a fresh database session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with overridden database dependency."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[__import__('app.db.session', fromlist=['get_db']).get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Sample user data for testing."""
    return {
        "name": "Test User",
        "email": "test@example.com",
        "password": "TestPassword123!",
    }


@pytest.fixture
def test_user(db_session, test_user_data):
    """Create a test user in the database."""
    user = create_user(
        db=db_session,
        user_data=UserCreate(**test_user_data),
        password_hash=hash_password(test_user_data["password"]),
    )
    return user


@pytest.fixture
def auth_headers(client, test_user_data):
    """Get authentication headers for test user."""
    # Register the user via API
    client.post("/api/v1/auth/register", json=test_user_data)

    # Login to get token
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user_data["email"], "password": test_user_data["password"]}
    )
    token = login_response.json()["token"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
