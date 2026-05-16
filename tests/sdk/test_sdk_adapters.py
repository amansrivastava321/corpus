"""Adapter integration tests — Anvil and Inspectra adapters against in-memory server."""

import pytest
from fastapi.testclient import TestClient

from corpus.adapters.anvil_adapter import AnvilAdapter
from corpus.adapters.inspectra_adapter import InspectraAdapter
from corpus.server import create_app
from corpus_sdk import CorpusClient, InProcessTransport


@pytest.fixture
def server():
    with TestClient(create_app(db_path=":memory:")) as tc:
        yield tc


def _make_anvil(server) -> AnvilAdapter:
    return AnvilAdapter.from_transport(InProcessTransport(server))


def _make_inspectra(server) -> InspectraAdapter:
    return InspectraAdapter.from_transport(InProcessTransport(server))


# ---------------------------------------------------------------------------
# Anvil adapter
# ---------------------------------------------------------------------------


class TestAnvilAdapter:
    def test_connect_registers_as_anvil(self, server):
        adapter = _make_anvil(server)
        product = adapter.connect()
        assert product.name == "Anvil"
        assert "BE_INTERRUPTED" in product.capabilities

    def test_notify_analysis_start(self, server):
        anvil = _make_anvil(server)
        anvil.connect()
        # Register Inspectra as target
        server.post("/products/register", json={"name": "Inspectra", "version": "1.0.0"})

        result = anvil.notify_analysis_start("auth", ["auth/login.py"])
        assert result.signal_type == "INFORM"

    def test_request_audit(self, server):
        anvil = _make_anvil(server)
        anvil.connect()
        server.post("/products/register", json={"name": "Inspectra", "version": "1.0.0"})

        result = anvil.request_audit("auth", ["auth/login.py"])
        assert result.signal_type == "VALIDATE"
        assert result.severity == "MEDIUM"

    def test_consult_on_change(self, server):
        anvil = _make_anvil(server)
        anvil.connect()
        server.post("/products/register", json={"name": "Inspectra", "version": "1.0.0"})

        result = anvil.consult_on_change(
            "Is JWT migration safe?", {"current": "uuid4", "target": "JWT"}
        )
        assert result.signal_type == "CONSULT"

    def test_broadcast_execution_start(self, server):
        anvil = _make_anvil(server)
        anvil.connect()
        inspectra = _make_inspectra(server)
        inspectra.connect()

        anvil.broadcast_execution_start("auth-refactor", {"pr": "42"})

        pending = server.get(f"/signals/pending/{inspectra.client.product_id}").json()
        assert len(pending) == 1
        assert pending[0]["payload"]["action"] == "execution_started"

    def test_receive_signals(self, server):
        anvil = _make_anvil(server)
        anvil.connect()
        inspectra = _make_inspectra(server)
        inspectra.connect()

        inspectra.raise_critical_finding("Anvil", "SQL injection", {"file": "auth/login.py:47"})

        signals = anvil.receive()
        assert len(signals) == 1
        assert signals[0].signal_type == "BLOCK"

    def test_process_pending_acknowledges(self, server):
        anvil = _make_anvil(server)
        anvil.connect()
        inspectra = _make_inspectra(server)
        inspectra.connect()

        inspectra.interrupt_execution("Anvil", "Risk detected")
        count = anvil.process_pending()
        assert count == 1
        assert len(anvil.receive()) == 0


# ---------------------------------------------------------------------------
# Inspectra adapter
# ---------------------------------------------------------------------------


class TestInspectraAdapter:
    def test_connect_registers_as_inspectra(self, server):
        adapter = _make_inspectra(server)
        product = adapter.connect()
        assert product.name == "Inspectra"
        assert "AUDIT" in product.capabilities
        assert "INTERRUPT" in product.capabilities

    def test_raise_critical_finding_blocks_target(self, server):
        inspectra = _make_inspectra(server)
        inspectra.connect()
        server.post("/products/register", json={"name": "Anvil", "version": "1.0.0"})

        result = inspectra.raise_critical_finding(
            "Anvil", "Hardcoded secret in auth/config.py", {"line": 12}
        )
        assert result.signal_type == "BLOCK"
        assert result.severity == "CRITICAL"

    def test_interrupt_execution(self, server):
        inspectra = _make_inspectra(server)
        inspectra.connect()
        server.post("/products/register", json={"name": "Anvil", "version": "1.0.0"})

        result = inspectra.interrupt_execution("Anvil", "SQL injection detected", severity="HIGH")
        assert result.signal_type == "INTERRUPT"
        assert result.severity == "HIGH"

    def test_share_pattern_broadcast(self, server):
        inspectra = _make_inspectra(server)
        inspectra.connect()
        anvil = _make_anvil(server)
        anvil.connect()

        inspectra.share_pattern(
            "hardcoded_secret", "Secret keys as string literals in config files"
        )

        pending = anvil.receive()
        assert len(pending) == 1
        assert pending[0].signal_type == "LEARN"

    def test_audit_complete_signal(self, server):
        inspectra = _make_inspectra(server)
        inspectra.connect()
        server.post("/products/register", json={"name": "Anvil", "version": "1.0.0"})

        result = inspectra.audit_complete(
            "Anvil", passed=False, findings=[{"type": "sql_injection", "severity": "HIGH"}]
        )
        assert result.signal_type == "INFORM"
        assert result.severity == "HIGH"
        payload = result.payload
        assert payload["passed"] is False
        assert payload["finding_count"] == 1

    def test_escalate_unresolved(self, server):
        inspectra = _make_inspectra(server)
        inspectra.connect()
        server.post("/products/register", json={"name": "Anvil", "version": "1.0.0"})

        result = inspectra.escalate_unresolved("Block unacknowledged", ["sig-001"])
        assert result.signal_type == "ESCALATE"
        assert result.broadcast is True


# ---------------------------------------------------------------------------
# Full end-to-end scenario: Inspectra → Corpus → Anvil
# ---------------------------------------------------------------------------


class TestEndToEndScenario:
    def test_security_finding_interrupts_anvil_execution(self, server):
        """
        Scenario:
          1. Anvil registers and starts working
          2. Inspectra registers and detects a critical auth vulnerability
          3. Inspectra emits a BLOCK signal to Anvil
          4. Anvil polls pending signals and sees the block
          5. Anvil acknowledges the signal
          6. Inspectra shares the pattern as a LEARN broadcast
        """
        # Step 1 — Anvil registers
        anvil = _make_anvil(server)
        anvil.connect(description="AI dev orchestration")
        assert anvil.is_connected

        # Step 2 — Inspectra registers
        inspectra = _make_inspectra(server)
        inspectra.connect(description="Autonomous audit")
        assert inspectra.is_connected

        # Step 3 — Inspectra finds a critical bug and blocks Anvil
        block_signal = inspectra.raise_critical_finding(
            "Anvil",
            "Hardcoded secret key in auth/config.py:12",
            {"cve": None, "line": 12, "file": "auth/config.py"},
        )
        assert block_signal.signal_type == "BLOCK"

        # Step 4 — Anvil polls and sees the block
        pending = anvil.receive()
        assert len(pending) == 1
        assert pending[0].signal_type == "BLOCK"
        assert "Hardcoded secret" in pending[0].payload["reason"]

        # Step 5 — Anvil acknowledges
        anvil.acknowledge(pending[0].id)
        assert len(anvil.receive()) == 0

        # Step 6 — Inspectra shares the pattern
        inspectra.share_pattern(
            "hardcoded_secret_in_config",
            "Secret keys defined as string literals instead of env vars",
        )
        # Anvil receives the LEARN broadcast
        learn_pending = anvil.receive()
        assert len(learn_pending) == 1
        assert learn_pending[0].signal_type == "LEARN"
