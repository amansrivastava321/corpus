"""Phase 13 — Integration adapter tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from corpus.server import create_app
from corpus_sdk import CorpusClient
from corpus_sdk.transport import InProcessTransport


@pytest.fixture
def client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


@pytest.fixture
def sdk_client(client):
    transport = InProcessTransport(client)
    sdk = CorpusClient(product_name="Anvil", transport=transport)
    sdk.connect()
    yield sdk
    sdk.disconnect()


# ─── Webhook mapping tests ────────────────────────────────────────────────────

class TestWebhookIntegration:
    def test_default_signal_map_built(self):
        from integrations.webhook.webhook_integration import WebhookCorpusIntegration, _DEFAULT_SIGNAL_MAP
        assert "push" in _DEFAULT_SIGNAL_MAP
        assert "deployment_status.failure" in _DEFAULT_SIGNAL_MAP
        assert "security_advisory" in _DEFAULT_SIGNAL_MAP

    def test_add_custom_mapping(self):
        from integrations.webhook.webhook_integration import WebhookCorpusIntegration
        integration = WebhookCorpusIntegration()
        integration.add_mapping("custom_event", "INFORM", "LOW")
        assert "custom_event" in integration._signal_map

    def test_unmapped_event_returns_none(self, client):
        from integrations.webhook.webhook_integration import WebhookCorpusIntegration
        transport = InProcessTransport(client)
        sdk = CorpusClient(product_name="Webhook", transport=transport)
        sdk.connect()
        try:
            integration = WebhookCorpusIntegration()
            integration._client = sdk
            integration._connected = True
            result = integration.handle_event("unknown_event_xyz", {})
            assert result is None
        finally:
            sdk.disconnect()


class TestAnvilIntegration:
    def test_integration_class_exists(self):
        from integrations.anvil.anvil_integration import AnvilCorpusIntegration
        assert AnvilCorpusIntegration is not None

    def test_integration_has_expected_methods(self):
        from integrations.anvil.anvil_integration import AnvilCorpusIntegration
        assert hasattr(AnvilCorpusIntegration, "connect")
        assert hasattr(AnvilCorpusIntegration, "task_started")
        assert hasattr(AnvilCorpusIntegration, "request_pre_deploy_clearance")
        assert hasattr(AnvilCorpusIntegration, "signal_audit_request")

    def test_task_started_emits_signal(self, client):
        from integrations.anvil.anvil_integration import AnvilCorpusIntegration
        integration = AnvilCorpusIntegration()
        transport = InProcessTransport(client)
        from corpus_sdk import CorpusClient
        sdk = CorpusClient(product_name="AnvilTest", transport=transport)
        sdk.connect()
        integration._client = sdk
        integration._connected = True
        result = integration.task_started("refactor auth", "auth.py")
        assert result is not None
        sdk.disconnect()


class TestInspectraIntegration:
    def test_integration_class_exists(self):
        from integrations.inspectra.inspectra_integration import InspectraCorpusIntegration
        assert InspectraCorpusIntegration is not None

    def test_has_expected_methods(self):
        from integrations.inspectra.inspectra_integration import InspectraCorpusIntegration
        assert hasattr(InspectraCorpusIntegration, "report_critical_finding")
        assert hasattr(InspectraCorpusIntegration, "report_warning")
        assert hasattr(InspectraCorpusIntegration, "share_pattern")


class TestGraphifyIntegration:
    def test_capabilities_declared(self):
        from integrations.graphify.graphify_integration import GraphifyCorpusIntegration
        assert "code_graph" in GraphifyCorpusIntegration.CAPABILITIES
        assert "impact_analysis" in GraphifyCorpusIntegration.CAPABILITIES


class TestCIIntegration:
    def test_capabilities_declared(self):
        from integrations.github_actions.ci_integration import CICorpusIntegration
        assert "ci_status" in CICorpusIntegration.CAPABILITIES
        assert "test_history" in CICorpusIntegration.CAPABILITIES


class TestNoCoreImports:
    """Verify integrations do NOT import Corpus internals."""

    def test_anvil_no_core_import(self):
        import ast
        import pathlib
        src = pathlib.Path("integrations/anvil/anvil_integration.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif node.module:
                    names = [node.module]
                for name in names:
                    assert not name.startswith("corpus."), (
                        f"Integration imports Corpus internal: {name}"
                    )

    def test_webhook_no_core_import(self):
        import ast
        import pathlib
        src = pathlib.Path("integrations/webhook/webhook_integration.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("corpus."), (
                    f"Webhook imports Corpus internal: {node.module}"
                )
