"""API integration tests (SQLite, same schema)."""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth(client):
    # SQLite dev-mode lifespan already bootstrapped the admin
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin@memespages.local",
                          "password": "change-me-strong-password"})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["database"] == "ok"


def test_auth_required(client):
    assert client.get("/api/v1/queue").status_code == 401


def test_login_wrong_password(client):
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin@memespages.local", "password": "wrong-pass"})
    assert r.status_code == 401


def test_account_lifecycle(client, auth):
    r = client.post("/api/v1/accounts",
                    json={"name": "Test", "platform": "custom", "username": "t1"},
                    headers=auth)
    assert r.status_code == 201
    aid = r.json()["id"]

    r = client.put(f"/api/v1/accounts/{aid}/settings",
                   json={"posting_limits": {"max_per_day": 3}}, headers=auth)
    assert r.json()["posting_limits"]["max_per_day"] == 3

    r = client.post(f"/api/v1/accounts/{aid}/automation",
                    json={"enabled": False}, headers=auth)
    assert r.json()["automation_enabled"] is False

    r = client.get("/api/v1/accounts", headers=auth)
    assert any(a["id"] == aid for a in r.json()["items"])

    r = client.delete(f"/api/v1/accounts/{aid}", headers=auth)
    assert r.status_code == 200


def test_sources_authorization_flow(client, auth):
    r = client.post("/api/v1/sources",
                    json={"name": "S", "source_type": "authorized_feed",
                          "url": "https://x.example.com/t.json",
                          "authorization": "authorized"}, headers=auth)
    sid = r.json()["id"]
    r = client.post(f"/api/v1/sources/{sid}/authorize",
                    json={"authorization": "not_authorized"}, headers=auth)
    assert r.json()["authorization"] == "not_authorized"
    r = client.post(f"/api/v1/sources/{sid}/authorize",
                    json={"authorization": "bogus"}, headers=auth)
    assert r.status_code == 422
    client.delete(f"/api/v1/sources/{sid}", headers=auth)


def test_settings_and_automation(client, auth):
    r = client.get("/api/v1/settings", headers=auth)
    assert "rules" in r.json() and "scheduler" in r.json()
    r = client.put("/api/v1/settings/rules", json={"min_trend_score": 90}, headers=auth)
    assert r.json()["min_trend_score"] == 90
    r = client.post("/api/v1/automation/start", headers=auth)
    assert r.json()["enabled"] is True
    r = client.get("/api/v1/automation/status", headers=auth)
    assert "Running" in r.json()["label"]
    client.post("/api/v1/automation/stop", headers=auth)


def test_reports_and_analytics(client, auth):
    assert client.get("/api/v1/analytics/overview", headers=auth).status_code == 200
    assert client.get("/api/v1/analytics/timeseries?days=7", headers=auth).status_code == 200
    r = client.post("/api/v1/reports/generate", json={"type": "daily"}, headers=auth)
    assert r.status_code == 200
    assert "MEMES PAGES DAILY REPORT" in r.json()["text_content"]
