"""
End-to-end API tests via FastAPI's TestClient (an in-process ASGI
client — no real server/port needed, but DOES need `fastapi` and
`httpx` installed, hence kept separate from `test_use_cases.py`).

    pip install -r backend/requirements.txt
    pytest tests/backend/test_api.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_is_public():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_protected_route_without_token_is_rejected():
    response = client.get("/api/v1/executive/months")
    assert response.status_code == 401


def test_login_with_bad_credentials_is_rejected():
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_login_and_access_protected_route():
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin#2026"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    months = client.get("/api/v1/executive/months", headers={"Authorization": f"Bearer {token}"})
    assert months.status_code == 200


def test_tampered_token_is_rejected():
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin#2026"})
    token = login.json()["access_token"]
    tampered = token[:-3] + "xyz"
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
