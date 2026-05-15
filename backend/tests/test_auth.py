"""Tests for authentication endpoints."""
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _register(email="test@example.com", password="password123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _login(email="test@example.com", password="password123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# ── register ──────────────────────────────────────────────────────────────────

def test_register_creates_user():
    res = _register()
    assert res.status_code == 201
    data = res.json()
    assert "token" in data
    assert data["email"] == "test@example.com"


def test_register_returns_jwt():
    res = _register(email="jwt@example.com")
    assert res.status_code == 201
    token = res.json()["token"]
    assert len(token) > 20
    assert token.count(".") == 2  # JWT has three segments


def test_register_duplicate_email_returns_409():
    _register(email="dup@example.com")
    res = _register(email="dup@example.com")
    assert res.status_code == 409


def test_register_normalises_email_to_lowercase():
    res = _register(email="Mixed@EXAMPLE.COM")
    assert res.status_code == 201
    assert res.json()["email"] == "mixed@example.com"


def test_register_short_password_rejected():
    res = _register(password="short")
    assert res.status_code == 422


# ── login ─────────────────────────────────────────────────────────────────────

def test_login_returns_token():
    _register(email="login@example.com")
    res = _login(email="login@example.com")
    assert res.status_code == 200
    assert "token" in res.json()


def test_login_wrong_password_returns_401():
    _register(email="wrongpw@example.com")
    res = _login(email="wrongpw@example.com", password="wrongpassword")
    assert res.status_code == 401


def test_login_short_password_returns_401_not_422():
    """Regression: login with a short password must return 401, not a 422 validation error.
    Previously LoginRequest shared min_length=8 with RegisterRequest, which caused FastAPI
    to return a 422 Pydantic error before checking credentials, crashing the React frontend."""
    _register(email="short@example.com")
    res = client.post("/api/auth/login", json={"email": "short@example.com", "password": "abc"})
    assert res.status_code == 401, (
        f"Expected 401, got {res.status_code}. "
        "A 422 here means the login model still has min_length validation."
    )


def test_login_unknown_email_returns_401():
    res = _login(email="nobody@example.com")
    assert res.status_code == 401


def test_login_email_case_insensitive():
    _register(email="case@example.com")
    res = client.post("/api/auth/login", json={"email": "CASE@EXAMPLE.COM", "password": "password123"})
    assert res.status_code == 200


# ── protected routes require auth ─────────────────────────────────────────────

def test_list_documents_without_auth_returns_401():
    res = client.get("/api/documents")
    assert res.status_code == 401


def test_list_documents_with_invalid_token_returns_401():
    res = client.get("/api/documents", headers={"Authorization": "Bearer invalid.token.here"})
    assert res.status_code == 401


def test_authenticated_request_succeeds():
    _register(email="auth@example.com")
    token = _login(email="auth@example.com").json()["token"]
    res = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)
