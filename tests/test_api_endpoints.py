"""Unit tests for FastAPI endpoints: /health, /webhooks/github, and /api/v1/analyze."""

import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)


def test_health_check_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ReqGuard AI"


def test_webhook_rejects_missing_signature():
    resp = client.post(
        "/webhooks/github",
        json={"action": "opened"},
        headers={"X-GitHub-Event": "pull_request"}
    )
    assert resp.status_code == 401
    assert "Invalid HMAC signature" in resp.json()["detail"]


def test_webhook_rejects_invalid_signature():
    resp = client.post(
        "/webhooks/github",
        json={"action": "opened"},
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=invalidhexsignature123456789"
        }
    )
    assert resp.status_code == 401


def test_webhook_ignores_unsupported_event():
    body = b'{"ref":"main"}'
    mac = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256)
    sig = f"sha256={mac.hexdigest()}"

    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json"
        }
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_manual_analysis_requires_auth():
    resp = client.post("/api/v1/analyze", json={"repo_full_name": "owner/repo", "pr_number": 1})
    assert resp.status_code == 401


def test_manual_analysis_rejects_invalid_token():
    resp = client.post(
        "/api/v1/analyze",
        json={"repo_full_name": "owner/repo", "pr_number": 1},
        headers={"Authorization": "Bearer wrong-token"}
    )
    assert resp.status_code == 403
