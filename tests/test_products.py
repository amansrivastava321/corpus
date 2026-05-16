"""Phase 1 — product registration and heartbeat tests."""

import pytest
from fastapi.testclient import TestClient

from corpus.server import create_app


@pytest.fixture
def client():
    """Fresh in-memory database per test."""
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


def _register(client: TestClient, name: str, version: str = "1.0.0", **kwargs) -> dict:
    payload = {"name": name, "version": version, **kwargs}
    resp = client.post("/products/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestProductRegistration:
    def test_register_success_returns_201(self, client):
        resp = client.post(
            "/products/register",
            json={"name": "Anvil", "version": "1.0.0"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Anvil"
        assert "product_id" in body
        assert body["status"] == "ACTIVE"

    def test_register_assigns_uuid(self, client):
        body = _register(client, "Inspectra")
        import uuid
        uuid.UUID(body["product_id"])  # raises if invalid

    def test_register_with_capabilities(self, client):
        body = _register(
            client,
            "Inspectra",
            capabilities=["EMIT_SIGNALS", "AUDIT", "INTERRUPT"],
        )
        assert set(body["capabilities"]) == {"EMIT_SIGNALS", "AUDIT", "INTERRUPT"}

    def test_register_duplicate_rejected(self, client):
        _register(client, "Anvil")
        resp = client.post("/products/register", json={"name": "Anvil", "version": "1.1.0"})
        assert resp.status_code == 409
        assert "already registered" in resp.json()["message"].lower()

    def test_register_duplicate_with_update_existing(self, client):
        first = _register(client, "Anvil", version="1.0.0")
        resp = client.post(
            "/products/register?update_existing=true",
            json={"name": "Anvil", "version": "1.1.0"},
        )
        assert resp.status_code == 201
        body = resp.json()
        # product_id preserved, version updated
        assert body["product_id"] == first["product_id"]
        assert body["version"] == "1.1.0"

    def test_register_empty_name_rejected(self, client):
        resp = client.post("/products/register", json={"name": "", "version": "1.0.0"})
        assert resp.status_code == 422  # Pydantic validation

    def test_register_missing_version_rejected(self, client):
        resp = client.post("/products/register", json={"name": "Anvil"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Listing and retrieval
# ---------------------------------------------------------------------------


class TestProductRetrieval:
    def test_list_products_empty(self, client):
        resp = client.get("/products")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_products_returns_all(self, client):
        _register(client, "Anvil")
        _register(client, "Inspectra")
        resp = client.get("/products")
        assert resp.status_code == 200
        names = {p["name"] for p in resp.json()}
        assert names == {"Anvil", "Inspectra"}

    def test_get_product_by_id(self, client):
        body = _register(client, "Anvil")
        pid = body["product_id"]
        resp = client.get(f"/products/{pid}")
        assert resp.status_code == 200
        assert resp.json()["product_id"] == pid

    def test_get_product_by_name(self, client):
        _register(client, "Anvil")
        resp = client.get("/products/Anvil")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Anvil"

    def test_get_nonexistent_product_returns_404(self, client):
        resp = client.get("/products/ghost-product")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_heartbeat_updates_last_seen(self, client):
        body = _register(client, "Anvil")
        pid = body["product_id"]
        assert body["last_seen"] is None  # never sent a heartbeat yet

        resp = client.post(
            f"/products/{pid}/heartbeat",
            json={"product_id": pid, "status": "ACTIVE"},
        )
        assert resp.status_code == 200
        assert resp.json()["last_seen"] is not None

    def test_heartbeat_updates_status(self, client):
        body = _register(client, "Anvil")
        pid = body["product_id"]

        resp = client.post(
            f"/products/{pid}/heartbeat",
            json={"product_id": pid, "status": "DEGRADED"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "DEGRADED"

    def test_heartbeat_for_unknown_product_returns_404(self, client):
        resp = client.post(
            "/products/no-such-product/heartbeat",
            json={"product_id": "no-such-product", "status": "ACTIVE"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Unregister
# ---------------------------------------------------------------------------


class TestUnregister:
    def test_unregister_removes_product(self, client):
        body = _register(client, "Anvil")
        pid = body["product_id"]
        resp = client.delete(f"/products/{pid}")
        assert resp.status_code == 204
        assert client.get(f"/products/{pid}").status_code == 404

    def test_unregister_unknown_returns_404(self, client):
        resp = client.delete("/products/ghost")
        assert resp.status_code == 404
