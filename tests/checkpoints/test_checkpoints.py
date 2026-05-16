"""Phase 4 — checkpoint interrupt engine tests."""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from corpus.server import create_app


@pytest.fixture
def client():
    """Fresh in-memory database per test."""
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


def _register(client: TestClient, name: str) -> dict:
    resp = client.post("/products/register", json={"name": name, "version": "1.0.0"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _emit_block(client: TestClient, source: str, target: str, severity: str = "CRITICAL") -> dict:
    resp = client.post(
        "/signals/emit",
        json={
            "type": "BLOCK",
            "severity": severity,
            "source_product": source,
            "target_product": target,
            "payload": {"reason": "test block"},
            "metadata": {"broadcast": False, "requires_ack": True, "tags": []},
        },
    )
    assert resp.status_code in (201, 202), resp.text
    return resp.json()


def _register_cp(
    client: TestClient,
    product_id: str,
    cp_type: str = "PRE_DEPLOY",
    timeout_policy: str = "FAIL_OPEN",
    timeout_seconds: int | None = None,
    context: dict | None = None,
) -> dict:
    body = {
        "product_id": product_id,
        "checkpoint_type": cp_type,
        "context": context or {},
        "timeout_policy": timeout_policy,
    }
    if timeout_seconds is not None:
        body["timeout_seconds"] = timeout_seconds
    resp = client.post("/checkpoints/register", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestCheckpointRegistration:
    def test_register_returns_201(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])
        assert cp["status"] == "REGISTERED"
        assert cp["product_id"] == product["product_id"]
        assert cp["checkpoint_type"] == "PRE_DEPLOY"
        assert "id" in cp

    def test_register_stores_context(self, client):
        product = _register(client, "Anvil")
        ctx = {"target": "production", "files": ["deploy.sh"]}
        cp = _register_cp(client, product["product_id"], context=ctx)
        assert cp["context"] == ctx

    def test_register_unknown_product_raises(self, client):
        resp = client.post(
            "/checkpoints/register",
            json={"product_id": "nonexistent-id", "checkpoint_type": "TEST", "context": {}},
        )
        assert resp.status_code in (400, 404)

    def test_get_checkpoint(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])
        resp = client.get(f"/checkpoints/{cp['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == cp["id"]
        assert data["status"] == "REGISTERED"

    def test_list_checkpoints_empty(self, client):
        resp = client.get("/checkpoints")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_checkpoints_filtered_by_product(self, client):
        p1 = _register(client, "Anvil")
        p2 = _register(client, "Inspectra")
        _register_cp(client, p1["product_id"])
        _register_cp(client, p2["product_id"])

        resp = client.get(f"/checkpoints?product_id={p1['product_id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["product_id"] == p1["product_id"]

    def test_list_checkpoints_filtered_by_status(self, client):
        product = _register(client, "Anvil")
        _register_cp(client, product["product_id"])
        _register_cp(client, product["product_id"])

        resp = client.get("/checkpoints?status=REGISTERED")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp = client.get("/checkpoints?status=CLEARED")
        assert resp.json() == []

    def test_get_nonexistent_checkpoint(self, client):
        resp = client.get("/checkpoints/does-not-exist")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Clearance — ALLOW path
# ---------------------------------------------------------------------------


class TestClearanceAllow:
    def test_request_clearance_no_signals_allows(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])

        resp = client.post(f"/checkpoints/{cp['id']}/request-clearance")
        assert resp.status_code == 200
        decision = resp.json()
        assert decision["decision_type"] == "ALLOW"
        assert decision["allows_continuation"] is True
        assert decision["is_blocking"] is False

    def test_checkpoint_status_becomes_cleared_on_allow(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])
        client.post(f"/checkpoints/{cp['id']}/request-clearance")

        resp = client.get(f"/checkpoints/{cp['id']}")
        assert resp.json()["status"] == "CLEARED"

    def test_get_decision_after_clearance(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])
        client.post(f"/checkpoints/{cp['id']}/request-clearance")

        resp = client.get(f"/checkpoints/{cp['id']}/decision")
        assert resp.status_code == 200
        d = resp.json()
        assert d["decision_type"] == "ALLOW"
        assert d["checkpoint_id"] == cp["id"]


# ---------------------------------------------------------------------------
# Clearance — BLOCK path
# ---------------------------------------------------------------------------


class TestClearanceBlock:
    def test_block_signal_causes_block_decision(self, client):
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")

        # Inspectra emits BLOCK at Anvil
        _emit_block(client, inspectra["name"], anvil["product_id"])

        cp = _register_cp(client, anvil["product_id"])
        resp = client.post(f"/checkpoints/{cp['id']}/request-clearance")
        assert resp.status_code == 200
        decision = resp.json()
        assert decision["decision_type"] == "BLOCK"
        assert decision["is_blocking"] is True
        assert decision["allows_continuation"] is False

    def test_checkpoint_status_blocked_after_block_decision(self, client):
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")
        _emit_block(client, inspectra["name"], anvil["product_id"])

        cp = _register_cp(client, anvil["product_id"])
        client.post(f"/checkpoints/{cp['id']}/request-clearance")

        resp = client.get(f"/checkpoints/{cp['id']}")
        assert resp.json()["status"] == "BLOCKED"

    def test_block_decision_has_trigger_signal(self, client):
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")
        signal = _emit_block(client, inspectra["name"], anvil["product_id"])

        cp = _register_cp(client, anvil["product_id"])
        client.post(f"/checkpoints/{cp['id']}/request-clearance")
        decision = client.get(f"/checkpoints/{cp['id']}/decision").json()
        assert decision["trigger_signal_id"] == signal["id"]

    def test_no_block_without_target_matching(self, client):
        inspectra = _register(client, "Inspectra")
        other = _register(client, "OtherProduct")
        anvil = _register(client, "Anvil")

        # Block targets OtherProduct, not Anvil
        _emit_block(client, inspectra["name"], other["product_id"])

        cp = _register_cp(client, anvil["product_id"])
        resp = client.post(f"/checkpoints/{cp['id']}/request-clearance")
        assert resp.json()["decision_type"] == "ALLOW"


# ---------------------------------------------------------------------------
# Resolution and cancellation
# ---------------------------------------------------------------------------


class TestCheckpointLifecycle:
    def test_resolve_checkpoint(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])
        client.post(f"/checkpoints/{cp['id']}/request-clearance")

        resp = client.post(f"/checkpoints/{cp['id']}/resolve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "RESOLVED"
        assert resp.json()["resolved_at"] is not None

    def test_cancel_checkpoint(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])

        resp = client.post(f"/checkpoints/{cp['id']}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"

    def test_resolve_updates_persisted_status(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])
        client.post(f"/checkpoints/{cp['id']}/request-clearance")
        client.post(f"/checkpoints/{cp['id']}/resolve")

        resp = client.get(f"/checkpoints/{cp['id']}")
        assert resp.json()["status"] == "RESOLVED"


# ---------------------------------------------------------------------------
# Audit history
# ---------------------------------------------------------------------------


class TestCheckpointHistory:
    def test_history_contains_registered_event(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])

        resp = client.get(f"/checkpoints/{cp['id']}/history")
        assert resp.status_code == 200
        events = resp.json()
        types = [e["event_type"] for e in events]
        assert "REGISTERED" in types

    def test_history_grows_with_lifecycle(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])
        client.post(f"/checkpoints/{cp['id']}/request-clearance")
        client.post(f"/checkpoints/{cp['id']}/resolve")

        resp = client.get(f"/checkpoints/{cp['id']}/history")
        events = resp.json()
        types = [e["event_type"] for e in events]
        assert "REGISTERED" in types
        assert "CLEARANCE_REQUESTED" in types
        assert "CLEARANCE_DECIDED" in types
        assert "RESOLVED" in types

    def test_history_is_ordered_chronologically(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])
        client.post(f"/checkpoints/{cp['id']}/request-clearance")
        client.post(f"/checkpoints/{cp['id']}/resolve")

        events = client.get(f"/checkpoints/{cp['id']}/history").json()
        timestamps = [e["occurred_at"] for e in events]
        assert timestamps == sorted(timestamps)

    def test_history_for_nonexistent_checkpoint(self, client):
        resp = client.get("/checkpoints/ghost-id/history")
        assert resp.status_code == 400

    def test_decision_not_found_before_clearance(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])

        resp = client.get(f"/checkpoints/{cp['id']}/decision")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Timeout policies
# ---------------------------------------------------------------------------


class TestTimeoutPolicies:
    def test_fail_open_allows_on_timeout(self, client):
        product = _register(client, "Anvil")
        # timeout_seconds=0 forces immediate expiry
        cp = _register_cp(
            client, product["product_id"],
            timeout_seconds=0, timeout_policy="FAIL_OPEN"
        )
        resp = client.post(f"/checkpoints/{cp['id']}/request-clearance")
        assert resp.json()["decision_type"] == "ALLOW"

        resp = client.get(f"/checkpoints/{cp['id']}")
        assert resp.json()["status"] == "EXPIRED"

    def test_fail_closed_blocks_on_timeout(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(
            client, product["product_id"],
            timeout_seconds=0, timeout_policy="FAIL_CLOSED"
        )
        resp = client.post(f"/checkpoints/{cp['id']}/request-clearance")
        assert resp.json()["decision_type"] == "BLOCK"
        assert resp.json()["is_blocking"] is True

    def test_escalate_policy_on_timeout(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(
            client, product["product_id"],
            timeout_seconds=0, timeout_policy="ESCALATE"
        )
        resp = client.post(f"/checkpoints/{cp['id']}/request-clearance")
        assert resp.json()["decision_type"] == "ESCALATE"


# ---------------------------------------------------------------------------
# WebSocket delivery of checkpoint events
# ---------------------------------------------------------------------------


class TestCheckpointWebSocketDelivery:
    def test_clearance_decision_pushed_to_connected_product(self, client):
        product = _register(client, "Anvil")
        product_id = product["product_id"]

        received = []
        ready = threading.Event()
        done = threading.Event()

        def ws_thread():
            with client.websocket_connect(f"/ws/products/{product_id}") as ws:
                # Consume CONNECTED handshake
                ws.receive_json()
                ready.set()
                # Wait for the clearance decision push
                msg = ws.receive_json()
                received.append(msg)
                done.set()

        t = threading.Thread(target=ws_thread, daemon=True)
        t.start()
        ready.wait(timeout=3)

        cp = _register_cp(client, product_id)
        client.post(f"/checkpoints/{cp['id']}/request-clearance")

        done.wait(timeout=3)
        t.join(timeout=1)

        assert len(received) == 1
        msg = received[0]
        assert msg["message_type"] in ("CLEARANCE_DECISION", "EXECUTION_BLOCKED")
        assert msg["checkpoint_id"] == cp["id"]

    def test_block_decision_pushed_as_execution_blocked(self, client):
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")
        product_id = anvil["product_id"]

        _emit_block(client, inspectra["name"], product_id)

        received = []
        ready = threading.Event()
        done = threading.Event()

        def ws_thread():
            with client.websocket_connect(f"/ws/products/{product_id}") as ws:
                ws.receive_json()  # CONNECTED
                ready.set()
                # Drain until we see EXECUTION_BLOCKED (pending signal flush arrives first)
                for _ in range(5):
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg.get("message_type") == "EXECUTION_BLOCKED":
                        done.set()
                        break

        t = threading.Thread(target=ws_thread, daemon=True)
        t.start()
        ready.wait(timeout=3)

        cp = _register_cp(client, product_id)
        client.post(f"/checkpoints/{cp['id']}/request-clearance")

        done.wait(timeout=3)
        t.join(timeout=1)

        blocked = [m for m in received if m.get("message_type") == "EXECUTION_BLOCKED"]
        assert len(blocked) == 1
        assert blocked[0]["allows_continuation"] is False

    def test_no_push_when_product_not_connected(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])
        # Should not raise even though product is offline
        resp = client.post(f"/checkpoints/{cp['id']}/request-clearance")
        assert resp.status_code == 200
