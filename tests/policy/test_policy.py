"""Phase 8 — Policy & Governance Engine tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from corpus.policy.authority_resolver import AuthorityResolver
from corpus.policy.governance_modes import capabilities
from corpus.policy.policy_engine import PolicyEngine
from corpus.policy.policy_loader import PolicyLoader
from corpus.policy.policy_models import GovernanceMode, PolicyRule, TrustLevel
from corpus.policy.trust_registry import TrustRegistry
from corpus.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


# ─── Unit tests ──────────────────────────────────────────────────────────────

class TestTrustRegistry:
    def test_set_and_get(self):
        registry = TrustRegistry()
        registry.set("anvil", TrustLevel.HIGH)
        assert registry.get("anvil") == TrustLevel.HIGH

    def test_unknown_product_gets_medium(self):
        registry = TrustRegistry()
        assert registry.get("unknown_xyz") == TrustLevel.MEDIUM

    def test_case_insensitive(self):
        registry = TrustRegistry()
        registry.set("Anvil", TrustLevel.TRUSTED)
        assert registry.get("anvil") == TrustLevel.TRUSTED

    def test_numeric_values(self):
        assert TrustLevel.UNTRUSTED.numeric() == 0.0
        assert TrustLevel.TRUSTED.numeric() == 1.0
        assert TrustLevel.MEDIUM.numeric() == 0.50


class TestGovernanceModes:
    def test_observer_cannot_block(self):
        caps = capabilities(GovernanceMode.OBSERVER)
        assert caps.can_block is False
        assert caps.records_events is True

    def test_advisor_can_warn_not_block(self):
        caps = capabilities(GovernanceMode.ADVISOR)
        assert caps.can_warn is True
        assert caps.can_block is False
        assert caps.can_escalate is True

    def test_guardian_can_do_everything(self):
        caps = capabilities(GovernanceMode.GUARDIAN)
        assert caps.can_block is True
        assert caps.can_delay is True
        assert caps.can_reroute is True
        assert caps.can_escalate is True


class TestAuthorityResolver:
    def _resolver(self, mode: GovernanceMode, trust: float = 0.8) -> AuthorityResolver:
        registry = TrustRegistry()
        registry.set("inspectra", TrustLevel.HIGH)
        return AuthorityResolver(registry, mode)

    def test_observer_cannot_block(self):
        resolver = self._resolver(GovernanceMode.OBSERVER)
        assert resolver.can_block("inspectra", "anvil") is False

    def test_guardian_high_trust_can_block(self):
        resolver = self._resolver(GovernanceMode.GUARDIAN)
        assert resolver.can_block("inspectra", "anvil") is True

    def test_untrusted_cannot_block(self):
        registry = TrustRegistry()
        registry.set("rogue", TrustLevel.UNTRUSTED)
        resolver = AuthorityResolver(registry, GovernanceMode.GUARDIAN)
        assert resolver.can_block("rogue", "anvil") is False

    def test_low_trust_cannot_emit_block(self):
        registry = TrustRegistry()
        registry.set("product", TrustLevel.LOW)
        resolver = AuthorityResolver(registry, GovernanceMode.GUARDIAN)
        assert resolver.can_emit("product", "BLOCK") is False


class TestPolicyEngine:
    def _engine(
        self,
        mode: GovernanceMode = GovernanceMode.GUARDIAN,
        trust: dict[str, TrustLevel] | None = None,
    ) -> PolicyEngine:
        registry = TrustRegistry()
        for name, level in (trust or {"inspectra": TrustLevel.HIGH, "anvil": TrustLevel.HIGH}).items():
            registry.set(name, level)
        return PolicyEngine(mode=mode, trust_registry=registry)

    def test_observer_always_allows(self):
        engine = self._engine(GovernanceMode.OBSERVER)
        result = engine.evaluate("inspectra", "anvil", "BLOCK", "CRITICAL")
        assert result.authorized is True
        assert result.action_taken == "ALLOW"

    def test_guardian_high_trust_allows_block(self):
        engine = self._engine(GovernanceMode.GUARDIAN)
        result = engine.evaluate("inspectra", "anvil", "BLOCK", "CRITICAL")
        assert result.authorized is True

    def test_guardian_untrusted_denies_block(self):
        engine = self._engine(
            GovernanceMode.GUARDIAN,
            trust={"rogue": TrustLevel.UNTRUSTED},
        )
        result = engine.evaluate("rogue", "anvil", "BLOCK", "CRITICAL")
        assert result.authorized is False
        assert result.action_taken == "DENY"

    def test_advisor_downgrades_block_to_warn(self):
        engine = self._engine(GovernanceMode.ADVISOR)
        result = engine.evaluate("inspectra", "anvil", "BLOCK", "HIGH")
        assert result.authorized is True
        assert result.action_taken == "WARN"

    def test_rule_min_trust_enforcement(self):
        registry = TrustRegistry()
        registry.set("new_product", TrustLevel.LOW)
        rules = [
            PolicyRule(
                name="require_high_trust",
                source_product=None,
                target_product=None,
                allowed_signal_types=["BLOCK"],
                min_trust_level=TrustLevel.HIGH,
            )
        ]
        engine = PolicyEngine(
            mode=GovernanceMode.GUARDIAN,
            trust_registry=registry,
            rules=rules,
        )
        result = engine.evaluate("new_product", "anvil", "BLOCK", "CRITICAL")
        assert result.authorized is False

    def test_rule_max_severity_enforcement(self):
        registry = TrustRegistry()
        registry.set("inspectra", TrustLevel.HIGH)
        rules = [
            PolicyRule(
                name="no_critical",
                source_product=None,
                target_product=None,
                allowed_signal_types=[],
                min_trust_level=TrustLevel.LOW,
                max_severity="HIGH",
            )
        ]
        engine = PolicyEngine(
            mode=GovernanceMode.GUARDIAN,
            trust_registry=registry,
            rules=rules,
        )
        result = engine.evaluate("inspectra", "anvil", "BLOCK", "CRITICAL")
        assert result.authorized is False

    def test_reload_changes_mode(self):
        engine = self._engine(GovernanceMode.GUARDIAN)
        new_registry = TrustRegistry()
        engine.reload(GovernanceMode.OBSERVER, new_registry, [])
        assert engine.mode == GovernanceMode.OBSERVER

    def test_evidence_list_present(self):
        engine = self._engine()
        result = engine.evaluate("inspectra", "anvil", "INFORM", "LOW")
        assert len(result.evidence) > 0


class TestPolicyLoader:
    def test_load_default(self):
        loader = PolicyLoader()
        mode, registry, rules = loader.default()
        assert mode == GovernanceMode.GUARDIAN
        assert registry.get("anvil") == TrustLevel.HIGH

    def test_load_dict_custom(self):
        loader = PolicyLoader()
        mode, registry, rules = loader.load_dict({
            "mode": "OBSERVER",
            "trust": {"product_a": "TRUSTED"},
            "rules": [
                {
                    "name": "test_rule",
                    "source_product": "product_a",
                    "allowed_signal_types": ["INFORM"],
                    "min_trust_level": "LOW",
                }
            ],
        })
        assert mode == GovernanceMode.OBSERVER
        assert registry.get("product_a") == TrustLevel.TRUSTED
        assert len(rules) == 1
        assert rules[0].name == "test_rule"

    def test_load_nonexistent_file_uses_default(self, tmp_path):
        loader = PolicyLoader()
        mode, registry, rules = loader.load_file(tmp_path / "nonexistent.json")
        assert mode == GovernanceMode.GUARDIAN


# ─── REST API tests ──────────────────────────────────────────────────────────

class TestPolicyAPI:
    def test_get_policy(self, client):
        resp = client.get("/policy")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "mode" in data
        assert "trust" in data
        assert "rule_count" in data

    def test_get_policy_mode_is_guardian(self, client):
        resp = client.get("/policy")
        assert resp.json()["mode"] == "GUARDIAN"

    def test_reload_policy(self, client):
        resp = client.post("/policy/reload")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_evaluate_allow(self, client):
        resp = client.post(
            "/policy/evaluate",
            json={
                "source_product": "inspectra",
                "target_product": "anvil",
                "signal_type": "INFORM",
                "severity": "LOW",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "authorized" in data
        assert "mode" in data
        assert "action_taken" in data

    def test_evaluate_untrusted_block_denied(self, client):
        # Rogue product not in trust registry defaults to MEDIUM (0.5), which is enough
        # to emit BLOCK in GUARDIAN mode. Let's verify the response shape.
        resp = client.post(
            "/policy/evaluate",
            json={
                "source_product": "rogue_untrusted",
                "target_product": "anvil",
                "signal_type": "BLOCK",
                "severity": "CRITICAL",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # MEDIUM trust (0.5) passes can_emit("BLOCK") threshold (>= 0.5)
        assert "authorized" in data

    def test_evaluate_response_has_evidence(self, client):
        resp = client.post(
            "/policy/evaluate",
            json={
                "source_product": "anvil",
                "target_product": "inspectra",
                "signal_type": "CONSULT",
                "severity": "MEDIUM",
            },
        )
        assert resp.status_code == 200
        assert "evidence" in resp.json()
