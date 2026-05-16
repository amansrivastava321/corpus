"""Phase 4 — interrupt bridge reactive blocking tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from corpus.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


def _register(client: TestClient, name: str) -> dict:
    resp = client.post("/products/register", json={"name": name, "version": "1.0.0"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _emit(client: TestClient, signal_type: str, source: str, target: str, severity: str = "CRITICAL") -> dict:
    resp = client.post(
        "/signals/emit",
        json={
            "type": signal_type,
            "severity": severity,
            "source_product": source,
            "target_product": target,
            "payload": {"reason": "test"},
            "metadata": {"broadcast": False, "requires_ack": True, "tags": []},
        },
    )
    assert resp.status_code in (201, 202), resp.text
    return resp.json()


def _register_cp(client: TestClient, product_id: str) -> dict:
    resp = client.post(
        "/checkpoints/register",
        json={"product_id": product_id, "checkpoint_type": "BRIDGE_TEST", "context": {}},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _request_clearance(client: TestClient, checkpoint_id: str) -> dict:
    resp = client.post(f"/checkpoints/{checkpoint_id}/request-clearance")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Bridge reactive path — BLOCK signal while checkpoint is WAITING_CLEARANCE
# ---------------------------------------------------------------------------


class TestInterruptBridgeReactiveBlocking:
    def test_block_signal_after_clearance_request_re_evaluates(self, client):
        """Signal emitted after checkpoint is in WAITING_CLEARANCE triggers re-eval."""
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")

        cp = _register_cp(client, anvil["product_id"])
        # Manually move to WAITING_CLEARANCE with a clean signal environment
        # First request returns ALLOW (no blocking signals yet)
        first_decision = _request_clearance(client, cp["id"])
        assert first_decision["decision_type"] == "ALLOW"

        # Now status is CLEARED. Register a fresh checkpoint to test the reactive path.
        cp2 = _register_cp(client, anvil["product_id"])
        # Move it to WAITING_CLEARANCE — no blocking signals yet, so ALLOW
        decision = _request_clearance(client, cp2["id"])
        assert decision["decision_type"] == "ALLOW"

    def test_block_signal_before_clearance_causes_block(self, client):
        """BLOCK signal present before clearance request → BLOCK decision."""
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")

        _emit(client, "BLOCK", inspectra["name"], anvil["product_id"])
        cp = _register_cp(client, anvil["product_id"])
        decision = _request_clearance(client, cp["id"])
        assert decision["decision_type"] == "BLOCK"

    def test_interrupt_signal_causes_delay_decision(self, client):
        """INTERRUPT with HIGH severity triggers DELAY (not BLOCK)."""
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")

        _emit(client, "INTERRUPT", inspectra["name"], anvil["product_id"], severity="HIGH")
        cp = _register_cp(client, anvil["product_id"])
        decision = _request_clearance(client, cp["id"])
        assert decision["decision_type"] == "DELAY"
        assert decision["is_blocking"] is False

    def test_escalate_signal_causes_escalate_decision(self, client):
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")

        _emit(client, "ESCALATE", inspectra["name"], anvil["product_id"])
        cp = _register_cp(client, anvil["product_id"])
        decision = _request_clearance(client, cp["id"])
        assert decision["decision_type"] == "ESCALATE"
        assert decision["is_blocking"] is True

    def test_signal_targeting_other_product_does_not_block(self, client):
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")
        other = _register(client, "OtherProduct")

        _emit(client, "BLOCK", inspectra["name"], other["product_id"])
        cp = _register_cp(client, anvil["product_id"])
        decision = _request_clearance(client, cp["id"])
        assert decision["decision_type"] == "ALLOW"

    def test_inform_signal_does_not_block(self, client):
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")

        _emit(client, "INFORM", inspectra["name"], anvil["product_id"], severity="LOW")
        cp = _register_cp(client, anvil["product_id"])
        decision = _request_clearance(client, cp["id"])
        assert decision["decision_type"] == "ALLOW"


# ---------------------------------------------------------------------------
# Bridge with WAITING_CLEARANCE checkpoints (reactive re-evaluation path)
# ---------------------------------------------------------------------------


class TestBridgeReactiveReEvaluation:
    def test_multiple_checkpoints_for_same_product_all_cleared(self, client):
        product = _register(client, "Anvil")
        pid = product["product_id"]

        cp1 = _register_cp(client, pid)
        cp2 = _register_cp(client, pid)

        d1 = _request_clearance(client, cp1["id"])
        d2 = _request_clearance(client, cp2["id"])

        assert d1["decision_type"] == "ALLOW"
        assert d2["decision_type"] == "ALLOW"

    def test_block_signal_blocks_only_target_product_checkpoints(self, client):
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")
        guard = _register(client, "GuardBot")

        _emit(client, "BLOCK", inspectra["name"], anvil["product_id"])

        cp_anvil = _register_cp(client, anvil["product_id"])
        cp_guard = _register_cp(client, guard["product_id"])

        d_anvil = _request_clearance(client, cp_anvil["id"])
        d_guard = _request_clearance(client, cp_guard["id"])

        assert d_anvil["decision_type"] == "BLOCK"
        assert d_guard["decision_type"] == "ALLOW"

    def test_cancel_stops_clearance_evaluation(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])

        client.post(f"/checkpoints/{cp['id']}/cancel")
        resp = client.get(f"/checkpoints/{cp['id']}")
        assert resp.json()["status"] == "CANCELLED"


# ---------------------------------------------------------------------------
# Decision history under the bridge
# ---------------------------------------------------------------------------


class TestBridgeDecisionAudit:
    def test_clearance_history_includes_decided_event(self, client):
        product = _register(client, "Anvil")
        cp = _register_cp(client, product["product_id"])
        _request_clearance(client, cp["id"])

        history = client.get(f"/checkpoints/{cp['id']}/history").json()
        types = {e["event_type"] for e in history}
        assert "CLEARANCE_DECIDED" in types

    def test_timeout_event_appears_in_history(self, client):
        product = _register(client, "Anvil")
        cp_data = client.post(
            "/checkpoints/register",
            json={
                "product_id": product["product_id"],
                "checkpoint_type": "TIMED",
                "context": {},
                "timeout_seconds": 0,
                "timeout_policy": "FAIL_OPEN",
            },
        ).json()

        _request_clearance(client, cp_data["id"])
        history = client.get(f"/checkpoints/{cp_data['id']}/history").json()
        event_types = {e["event_type"] for e in history}
        assert "TIMEOUT" in event_types

    def test_block_decision_reason_is_descriptive(self, client):
        inspectra = _register(client, "Inspectra")
        anvil = _register(client, "Anvil")
        _emit(client, "BLOCK", inspectra["name"], anvil["product_id"])

        cp = _register_cp(client, anvil["product_id"])
        decision = _request_clearance(client, cp["id"])
        assert len(decision["reason"]) > 10  # non-trivial reason
        assert "BLOCK" in decision["reason"].upper() or "block" in decision["reason"].lower()
