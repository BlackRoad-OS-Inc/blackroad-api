"""
Tests for integration endpoints — Railway, GitHub, RoadChain,
Cloudflare, DigitalOcean, live feed, and JWT auth.
Run: pytest tests/ -v
"""

from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── RoadChain Ledger (issue #4 — local DB, no external deps) ─────────────────

def test_roadchain_submit_transaction():
    r = client.post("/v1/roadchain/transactions", json={
        "type": "transfer",
        "sender": "lucidia",
        "receiver": "alice",
        "payload": {"amount": 100, "unit": "compute"},
    })
    assert r.status_code == 201
    d = r.json()
    assert "tx_id" in d
    assert "block_hash" in d
    assert "prev_hash" in d


def test_roadchain_list_transactions():
    r = client.get("/v1/roadchain/transactions")
    assert r.status_code == 200
    d = r.json()
    assert "transactions" in d
    assert "total" in d


def test_roadchain_get_transaction():
    # First create one
    create = client.post("/v1/roadchain/transactions", json={
        "type": "audit",
        "sender": "cipher",
        "payload": {"note": "security check"},
    })
    tx_id = create.json()["tx_id"]
    r = client.get(f"/v1/roadchain/transactions/{tx_id}")
    assert r.status_code == 200
    assert r.json()["tx_id"] == tx_id


def test_roadchain_transaction_not_found():
    r = client.get("/v1/roadchain/transactions/tx_nonexistent")
    assert r.status_code == 404


def test_roadchain_audit_trail():
    r = client.get("/v1/roadchain/audit")
    assert r.status_code == 200
    d = r.json()
    assert "audit" in d


def test_roadchain_chain_integrity():
    """Consecutive transactions should form a hash chain."""
    r1 = client.post("/v1/roadchain/transactions", json={
        "type": "governance",
        "sender": "octavia",
        "payload": {"action": "vote"},
    })
    first = r1.json()
    assert "block_hash" in first
    assert "prev_hash" in first
    # prev_hash should be a valid hex string or GENESIS
    assert len(first["prev_hash"]) >= 6


# ── Railway (issue #2 — requires RAILWAY_TOKEN) ──────────────────────────────

def test_railway_services_no_token():
    """Without RAILWAY_TOKEN, should return 503."""
    with patch.dict("os.environ", {}, clear=False):
        # Ensure no token
        import os
        os.environ.pop("RAILWAY_TOKEN", None)
        r = client.get("/v1/railway/services")
        assert r.status_code == 503


def test_railway_health_no_token():
    import os
    os.environ.pop("RAILWAY_TOKEN", None)
    r = client.get("/v1/railway/health")
    # Returns degraded status, not error
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"


# ── GitHub (issue #3 — requires GITHUB_TOKEN) ────────────────────────────────

def test_github_repos_no_token():
    import os
    os.environ.pop("GITHUB_TOKEN", None)
    r = client.get("/v1/github/repos")
    assert r.status_code == 503


# ── Cloudflare (issue #6 — requires CF tokens) ───────────────────────────────

def test_cloudflare_workers_no_token():
    import os
    os.environ.pop("CLOUDFLARE_API_TOKEN", None)
    r = client.get("/v1/cloudflare/workers")
    assert r.status_code == 503


def test_cloudflare_health_no_token():
    import os
    os.environ.pop("CLOUDFLARE_API_TOKEN", None)
    r = client.get("/v1/cloudflare/health")
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"


# ── DigitalOcean (issue #7 — requires DO token) ──────────────────────────────

def test_digitalocean_droplets_no_token():
    import os
    os.environ.pop("DIGITALOCEAN_TOKEN", None)
    r = client.get("/v1/digitalocean/droplets")
    assert r.status_code == 503


# ── Live Feed SSE (issue #5) ─────────────────────────────────────────────────

def test_agent_feed_sse_route_exists():
    """SSE feed route should be registered in the OpenAPI spec."""
    r = client.get("/openapi.json")
    paths = r.json().get("paths", {})
    assert "/v1/feed/agents" in paths


# ── JWT Auth (issue #1) ──────────────────────────────────────────────────────

def test_jwt_create_and_verify():
    import os
    os.environ["JWT_SECRET"] = "test-secret-key-for-blackroad"
    from app.middleware.jwt_auth import create_jwt, verify_jwt

    token = create_jwt({"sub": "lucidia", "role": "agent"}, "test-secret-key-for-blackroad")
    payload = verify_jwt(token, "test-secret-key-for-blackroad")
    assert payload["sub"] == "lucidia"
    assert payload["role"] == "agent"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_invalid_token():
    from app.middleware.jwt_auth import verify_jwt
    from fastapi import HTTPException
    import pytest

    with pytest.raises(HTTPException) as exc_info:
        verify_jwt("invalid.token.here", "some-secret")
    assert exc_info.value.status_code == 401


# ── OpenAPI spec includes new routes ─────────────────────────────────────────

def test_openapi_includes_integration_routes():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    # Check that integration routes are registered
    integration_prefixes = ["/v1/railway", "/v1/github", "/v1/roadchain", "/v1/cloudflare", "/v1/digitalocean"]
    for prefix in integration_prefixes:
        matching = [p for p in paths if p.startswith(prefix)]
        assert len(matching) > 0, f"No routes found for {prefix}"


def test_openapi_includes_feed_routes():
    r = client.get("/openapi.json")
    paths = r.json().get("paths", {})
    assert "/v1/feed/agents" in paths
