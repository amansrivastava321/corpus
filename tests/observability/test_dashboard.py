"""Phase 11 — Observability Dashboard tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from corpus.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


def _register(client, name: str) -> dict:
    resp = client.post("/products/register", json={"name": name, "version": "1.0.0"})
    assert resp.status_code == 201
    return resp.json()


class TestDashboardAPI:
    def test_summary_endpoint(self, client):
        resp = client.get("/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        assert "signals" in data
        assert "checkpoints" in data
        assert "policy" in data
        assert "guardian" in data
        assert "generated_at" in data

    def test_summary_product_counts(self, client):
        _register(client, "anvil")
        _register(client, "inspectra")
        resp = client.get("/dashboard/summary")
        assert resp.json()["products"]["total"] == 2

    def test_products_endpoint(self, client):
        _register(client, "anvil")
        resp = client.get("/dashboard/products")
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        assert "count" in data
        assert data["count"] >= 1

    def test_signals_endpoint(self, client):
        resp = client.get("/dashboard/signals")
        assert resp.status_code == 200
        assert "pending" in resp.json()

    def test_checkpoints_endpoint(self, client):
        resp = client.get("/dashboard/checkpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert "checkpoints" in data
        assert "by_status" in data

    def test_orchestrations_endpoint(self, client):
        resp = client.get("/dashboard/orchestrations")
        assert resp.status_code == 200
        data = resp.json()
        assert "workflows" in data
        assert "count" in data

    def test_guardian_endpoint(self, client):
        resp = client.get("/dashboard/guardian")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "interventions" in data

    def test_memory_endpoint(self, client):
        resp = client.get("/dashboard/memory")
        assert resp.status_code == 200
        data = resp.json()
        assert "episodes" in data
        assert "patterns" in data

    def test_audit_endpoint(self, client):
        resp = client.get("/dashboard/audit")
        assert resp.status_code == 200
        assert "audit_table" in resp.json()

    def test_timeline_endpoint(self, client):
        resp = client.get("/dashboard/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert "timeline" in data
        assert "count" in data

    def test_timeline_limit_param(self, client):
        resp = client.get("/dashboard/timeline", params={"limit": 5})
        assert resp.status_code == 200

    def test_policy_mode_shown_in_summary(self, client):
        resp = client.get("/dashboard/summary")
        assert resp.json()["policy"]["mode"] == "GUARDIAN"


class TestAdminAPI:
    def test_config_endpoint(self, client):
        resp = client.get("/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data

    def test_storage_health_endpoint(self, client):
        resp = client.get("/admin/storage/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_export_endpoint(self, client):
        resp = client.post("/admin/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "tables" in data
        assert "products" in data["tables"]

    def test_import_endpoint_is_cli_only(self, client):
        resp = client.post("/admin/import")
        assert resp.status_code == 200
