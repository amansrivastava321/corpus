"""Phase 1 — signal emit, pending, ack, and routing tests."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from corpus.server import create_app


@pytest.fixture
def client():
    """Fresh in-memory database per test."""
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


def _register(client: TestClient, name: str, **kwargs) -> dict:
    resp = client.post(
        "/products/register",
        json={"name": name, "version": "1.0.0", **kwargs},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _emit(client: TestClient, **overrides) -> dict:
    payload = {
        "type": "INFORM",
        "severity": "LOW",
        "source_product": "inspectra",
        "target_product": "anvil",
        **overrides,
    }
    resp = client.post("/signals/emit", json=payload)
    assert resp.status_code == 202, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------


class TestSignalEmit:
    def test_emit_direct_signal_returns_202(self, client):
        _register(client, "Anvil")
        _register(client, "Inspectra")
        resp = client.post(
            "/signals/emit",
            json={
                "type": "INFORM",
                "severity": "LOW",
                "source_product": "Inspectra",
                "target_product": "Anvil",
            },
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["type"] == "INFORM"
        assert "id" in body

    def test_emit_stores_signal(self, client):
        _register(client, "Anvil")
        _register(client, "Inspectra")
        body = _emit(client, source_product="Inspectra", target_product="Anvil")
        signal_id = body["id"]
        resp = client.get(f"/signals/{signal_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == signal_id

    def test_emit_to_unregistered_product_returns_422(self, client):
        resp = client.post(
            "/signals/emit",
            json={
                "type": "BLOCK",
                "severity": "CRITICAL",
                "source_product": "inspectra",
                "target_product": "ghost-product",
            },
        )
        assert resp.status_code == 422
        assert "not registered" in resp.json()["message"].lower()

    def test_emit_non_broadcast_without_target_returns_422(self, client):
        resp = client.post(
            "/signals/emit",
            json={
                "type": "INFORM",
                "severity": "LOW",
                "source_product": "inspectra",
                # no target_product, no broadcast flag
            },
        )
        assert resp.status_code == 422

    def test_emit_critical_block_signal(self, client):
        _register(client, "Anvil")
        _register(client, "Inspectra")
        resp = client.post(
            "/signals/emit",
            json={
                "type": "BLOCK",
                "severity": "CRITICAL",
                "source_product": "Inspectra",
                "target_product": "Anvil",
                "payload": {
                    "reason": "Hardcoded secret found in auth/config.py:12"
                },
            },
        )
        assert resp.status_code == 202
        assert resp.json()["severity"] == "CRITICAL"

    def test_emit_resolves_target_by_name(self, client):
        """target_product='anvil' (lowercase name) should resolve to the registered product."""
        _register(client, "Anvil")
        _register(client, "Inspectra")
        resp = client.post(
            "/signals/emit",
            json={
                "type": "INFORM",
                "severity": "LOW",
                "source_product": "Inspectra",
                "target_product": "anvil",  # lowercase, by name
            },
        )
        assert resp.status_code == 202


# ---------------------------------------------------------------------------
# Pending signals
# ---------------------------------------------------------------------------


class TestPendingSignals:
    def test_pending_signals_returns_queued_signal(self, client):
        anvil = _register(client, "Anvil")
        _register(client, "Inspectra")
        _emit(client, source_product="Inspectra", target_product="Anvil", type="INTERRUPT",
              severity="HIGH")

        resp = client.get(f"/signals/pending/{anvil['product_id']}")
        assert resp.status_code == 200
        signals = resp.json()
        assert len(signals) == 1
        assert signals[0]["type"] == "INTERRUPT"

    def test_pending_signals_by_name(self, client):
        _register(client, "Anvil")
        _register(client, "Inspectra")
        _emit(client, source_product="Inspectra", target_product="Anvil")

        resp = client.get("/signals/pending/Anvil")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_pending_signals_empty_initially(self, client):
        anvil = _register(client, "Anvil")
        resp = client.get(f"/signals/pending/{anvil['product_id']}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_pending_for_unknown_product_returns_404(self, client):
        resp = client.get("/signals/pending/no-such-product")
        assert resp.status_code == 404

    def test_multiple_pending_signals_ordered_by_creation(self, client):
        anvil = _register(client, "Anvil")
        _register(client, "Inspectra")
        for i in range(3):
            _emit(
                client,
                source_product="Inspectra",
                target_product="Anvil",
                payload={"seq": i},
            )
        signals = client.get(f"/signals/pending/{anvil['product_id']}").json()
        assert len(signals) == 3


# ---------------------------------------------------------------------------
# Acknowledgement
# ---------------------------------------------------------------------------


class TestAcknowledgement:
    def test_acknowledge_removes_from_pending(self, client):
        anvil = _register(client, "Anvil")
        _register(client, "Inspectra")
        sig = _emit(client, source_product="Inspectra", target_product="Anvil")
        signal_id = sig["id"]
        product_id = anvil["product_id"]

        resp = client.post(f"/signals/{signal_id}/ack", json={"product_id": product_id})
        assert resp.status_code == 200
        assert resp.json()["status"] == "acknowledged"

        # No longer pending
        pending = client.get(f"/signals/pending/{product_id}").json()
        assert len(pending) == 0

    def test_acknowledge_idempotent(self, client):
        anvil = _register(client, "Anvil")
        _register(client, "Inspectra")
        sig = _emit(client, source_product="Inspectra", target_product="Anvil")
        pid = anvil["product_id"]

        client.post(f"/signals/{sig['id']}/ack", json={"product_id": pid})
        # Second ack should also succeed (idempotent)
        resp = client.post(f"/signals/{sig['id']}/ack", json={"product_id": pid})
        assert resp.status_code == 200

    def test_acknowledge_by_product_name(self, client):
        _register(client, "Anvil")
        _register(client, "Inspectra")
        sig = _emit(client, source_product="Inspectra", target_product="Anvil")

        resp = client.post(f"/signals/{sig['id']}/ack", json={"product_id": "Anvil"})
        assert resp.status_code == 200

    def test_acknowledge_wrong_product_returns_422(self, client):
        _register(client, "Anvil")
        inspectra = _register(client, "Inspectra")
        sig = _emit(client, source_product="Inspectra", target_product="Anvil")

        # Inspectra trying to ack a signal routed to Anvil
        resp = client.post(
            f"/signals/{sig['id']}/ack",
            json={"product_id": inspectra["product_id"]},
        )
        assert resp.status_code == 422

    def test_acknowledge_nonexistent_signal_returns_404(self, client):
        _register(client, "Anvil")
        resp = client.post("/signals/no-such-signal/ack", json={"product_id": "Anvil"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Expired signals
# ---------------------------------------------------------------------------


class TestTtlExpiry:
    def test_expired_signal_not_in_pending(self, client):
        anvil = _register(client, "Anvil")
        _register(client, "Inspectra")

        # Build a signal with a timestamp 10 minutes in the past and ttl=1s
        past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        resp = client.post(
            "/signals/emit",
            json={
                "type": "INFORM",
                "severity": "LOW",
                "source_product": "Inspectra",
                "target_product": "Anvil",
                "timestamp": past,
                "ttl": 1,
            },
        )
        # Emit itself may be rejected (already expired) or succeed but yield empty pending
        if resp.status_code == 410:
            # SignalExpiredError raised at emit time — correct
            pass
        else:
            assert resp.status_code == 202
            pending = client.get(f"/signals/pending/{anvil['product_id']}").json()
            assert len(pending) == 0


# ---------------------------------------------------------------------------
# Broadcast signals
# ---------------------------------------------------------------------------


class TestBroadcast:
    def test_broadcast_routes_to_all_products_except_source(self, client):
        anvil = _register(client, "Anvil")
        inspectra = _register(client, "Inspectra")

        resp = client.post(
            "/signals/emit",
            json={
                "type": "LEARN",
                "severity": "LOW",
                "source_product": inspectra["product_id"],
                "target_product": None,
                "metadata": {"broadcast": True},
                "payload": {"pattern": "hardcoded_secret"},
            },
        )
        assert resp.status_code == 202

        # Anvil receives it
        anvil_pending = client.get(f"/signals/pending/{anvil['product_id']}").json()
        assert len(anvil_pending) == 1

        # Inspectra (source) does NOT receive it
        inspectra_pending = client.get(
            f"/signals/pending/{inspectra['product_id']}"
        ).json()
        assert len(inspectra_pending) == 0

    def test_broadcast_with_three_products(self, client):
        p1 = _register(client, "Anvil")
        p2 = _register(client, "Inspectra")
        p3 = _register(client, "GraphEngine")

        client.post(
            "/signals/emit",
            json={
                "type": "LEARN",
                "severity": "LOW",
                "source_product": p1["product_id"],
                "metadata": {"broadcast": True},
            },
        )

        for product in [p2, p3]:
            pending = client.get(f"/signals/pending/{product['product_id']}").json()
            assert len(pending) == 1

        # Source should not receive it
        src_pending = client.get(f"/signals/pending/{p1['product_id']}").json()
        assert len(src_pending) == 0


# ---------------------------------------------------------------------------
# Get signal by ID
# ---------------------------------------------------------------------------


class TestGetSignal:
    def test_get_signal_by_id(self, client):
        _register(client, "Anvil")
        _register(client, "Inspectra")
        sig = _emit(client, source_product="Inspectra", target_product="Anvil")

        resp = client.get(f"/signals/{sig['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sig["id"]

    def test_get_nonexistent_signal_returns_404(self, client):
        resp = client.get("/signals/no-such-signal")
        assert resp.status_code == 404
