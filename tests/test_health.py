"""Phase 1 — /health endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from corpus.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_status_is_ok(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"

    def test_health_contains_version(self, client):
        body = client.get("/health").json()
        assert "version" in body
        assert body["version"] == "0.1.0"

    def test_health_reports_zero_products_initially(self, client):
        body = client.get("/health").json()
        assert body["products_registered"] == 0

    def test_health_products_count_updates_after_registration(self, client):
        client.post("/products/register", json={"name": "Anvil", "version": "1.0.0"})
        client.post("/products/register", json={"name": "Inspectra", "version": "1.2.0"})
        body = client.get("/health").json()
        assert body["products_registered"] == 2

    def test_health_contains_uptime(self, client):
        body = client.get("/health").json()
        assert "uptime_seconds" in body
        assert body["uptime_seconds"] >= 0

    def test_health_contains_started_at(self, client):
        body = client.get("/health").json()
        assert "started_at" in body

    def test_health_contains_signal_counters(self, client):
        body = client.get("/health").json()
        assert "total_signals_received" in body
        assert "pending_deliveries" in body

    def test_health_signals_received_counter_increments(self, client):
        client.post("/products/register", json={"name": "Anvil", "version": "1.0.0"})
        client.post("/products/register", json={"name": "Inspectra", "version": "1.0.0"})
        client.post(
            "/signals/emit",
            json={
                "type": "INFORM",
                "severity": "LOW",
                "source_product": "Inspectra",
                "target_product": "Anvil",
            },
        )
        body = client.get("/health").json()
        assert body["total_signals_received"] == 1
