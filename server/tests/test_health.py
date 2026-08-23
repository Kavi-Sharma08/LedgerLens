"""Smoke tests for the API foundation.

These run without MongoDB: the app is designed to start in degraded mode,
so /api/health must still respond. Authentication lives in Next.js/Auth.js —
these tests also pin the FastAPI boundary contract.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_responds():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "LedgerLens API"
    assert body["database"] in {"connected", "unavailable"}


def test_no_auth_endpoints_remain():
    """Auth.js owns authentication; FastAPI must not expose auth routes."""
    with TestClient(app) as client:
        for path in (
            "/api/auth/session",
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/logout",
            "/api/auth/google/signin",
            "/api/auth/google/callback",
        ):
            assert client.post(path).status_code == 404, path
            assert client.get(path).status_code == 404, path


def test_protected_endpoint_rejects_missing_identity():
    with TestClient(app) as client:
        response = client.get("/api/users/me")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_protected_endpoint_rejects_spoofed_identity():
    """Identity headers without the internal secret must never authenticate."""
    with TestClient(app) as client:
        response = client.get(
            "/api/users/me",
            headers={"X-LL-User-Id": "000000000000000000000000"},
        )
    assert response.status_code == 401
