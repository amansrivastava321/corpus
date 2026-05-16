"""Phase 5 — Signal Gravity Engine tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from corpus.gravity.gravity_engine import GravityEngine
from corpus.gravity.gravity_rules import apply_rules
from corpus.gravity.gravity_score import GravityAction
from corpus.gravity.risk_context import RiskContext
from corpus.gravity.signal_prioritizer import SignalPrioritizer
from corpus.schemas import Signal, SignalSeverity, SignalType
from corpus.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


# ─── GravityEngine unit tests ───────────────────────────────────────────────

class TestGravityEngineUnit:
    def _signal(self, sig_type: str, severity: str) -> Signal:
        return Signal(
            type=SignalType(sig_type),
            severity=SignalSeverity(severity),
            source_product="inspectra",
            target_product="anvil",
        )

    def test_critical_block_scores_block_action(self):
        engine = GravityEngine()
        sig = self._signal("BLOCK", "CRITICAL")
        score = engine.evaluate(sig)
        assert score.action == GravityAction.BLOCK
        assert score.score > 0
        assert score.is_blocking is True

    def test_high_block_is_also_block(self):
        engine = GravityEngine()
        sig = self._signal("BLOCK", "HIGH")
        score = engine.evaluate(sig)
        assert score.action == GravityAction.BLOCK

    def test_escalate_maps_to_escalate(self):
        engine = GravityEngine()
        sig = self._signal("ESCALATE", "MEDIUM")
        score = engine.evaluate(sig)
        assert score.action == GravityAction.ESCALATE
        assert score.is_blocking is True

    def test_high_interrupt_maps_to_delay(self):
        engine = GravityEngine()
        sig = self._signal("INTERRUPT", "HIGH")
        score = engine.evaluate(sig)
        assert score.action == GravityAction.DELAY
        assert score.action.requires_checkpoint is True

    def test_inform_low_queues_or_ignores(self):
        engine = GravityEngine()
        sig = self._signal("INFORM", "LOW")
        score = engine.evaluate(sig)
        assert score.action in (GravityAction.QUEUE, GravityAction.IGNORE)
        assert score.is_blocking is False

    def test_evidence_list_populated(self):
        engine = GravityEngine()
        sig = self._signal("BLOCK", "CRITICAL")
        score = engine.evaluate(sig)
        assert len(score.evidence) >= 3
        assert any("base_weight" in e for e in score.evidence)

    def test_context_multiplier_raises_score(self):
        engine = GravityEngine()
        sig = self._signal("INTERRUPT", "HIGH")
        ctx_plain = RiskContext()
        ctx_charged = RiskContext(has_active_checkpoint=True, source_trust=1.0)
        plain_score = engine.evaluate(sig, ctx_plain)
        charged_score = engine.evaluate(sig, ctx_charged)
        assert charged_score.score > plain_score.score

    def test_low_trust_reduces_score(self):
        engine = GravityEngine()
        sig = self._signal("BLOCK", "HIGH")
        ctx_low_trust = RiskContext(source_trust=0.1)
        ctx_high_trust = RiskContext(source_trust=1.0)
        low = engine.evaluate(sig, ctx_low_trust)
        high = engine.evaluate(sig, ctx_high_trust)
        assert high.score > low.score

    def test_offline_target_reduces_score(self):
        engine = GravityEngine()
        sig = self._signal("BLOCK", "HIGH")
        online = engine.evaluate(sig, RiskContext(target_online=True))
        offline = engine.evaluate(sig, RiskContext(target_online=False))
        assert online.score > offline.score

    def test_signal_id_propagated(self):
        engine = GravityEngine()
        sig = self._signal("BLOCK", "CRITICAL")
        score = engine.evaluate(sig)
        assert score.signal_id == sig.id

    def test_confidence_in_range(self):
        engine = GravityEngine()
        for sig_type in ["BLOCK", "ESCALATE", "INTERRUPT", "INFORM"]:
            for sev in ["LOW", "HIGH", "CRITICAL"]:
                sig = self._signal(sig_type, sev)
                score = engine.evaluate(sig)
                assert 0.0 <= score.confidence <= 1.0


class TestGravityRules:
    def test_critical_block_rule_returns_correct_action(self):
        from corpus.schemas import SignalSeverity, SignalType
        result = apply_rules(SignalType.BLOCK, SignalSeverity.CRITICAL, 30.0)
        assert result is not None
        assert result.action == GravityAction.BLOCK

    def test_low_weight_no_match(self):
        from corpus.schemas import SignalSeverity, SignalType
        result = apply_rules(SignalType.INFORM, SignalSeverity.LOW, 0.1)
        assert result is None or result.action in (GravityAction.QUEUE, GravityAction.IGNORE)


class TestSignalPrioritizer:
    def _signal(self, sig_type: str, severity: str) -> Signal:
        return Signal(
            type=SignalType(sig_type),
            severity=SignalSeverity(severity),
            source_product="inspectra",
            target_product="anvil",
        )

    def test_rank_orders_by_score_descending(self):
        prioritizer = SignalPrioritizer()
        signals = [
            self._signal("INFORM", "LOW"),
            self._signal("BLOCK", "CRITICAL"),
            self._signal("INTERRUPT", "HIGH"),
        ]
        ranked = prioritizer.rank(signals)
        scores = [s.score for _, s in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_top_returns_correct_count(self):
        prioritizer = SignalPrioritizer()
        signals = [self._signal("BLOCK", "CRITICAL"), self._signal("INFORM", "LOW")]
        top = prioritizer.top(signals, n=1)
        assert len(top) == 1
        assert top[0][1].action == GravityAction.BLOCK


# ─── REST API tests ──────────────────────────────────────────────────────────

class TestGravityAPI:
    def _signal_dict(self, sig_type: str = "BLOCK", severity: str = "CRITICAL") -> dict:
        return {
            "type": sig_type,
            "severity": severity,
            "source_product": "inspectra",
            "target_product": "anvil",
        }

    def test_evaluate_critical_block(self, client):
        resp = client.post(
            "/gravity/evaluate",
            json={"signal": self._signal_dict()},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["action"] == "BLOCK"
        assert data["is_blocking"] is True
        assert data["score"] > 0
        assert "confidence" in data
        assert "evidence" in data

    def test_evaluate_inform_low(self, client):
        resp = client.post(
            "/gravity/evaluate",
            json={"signal": self._signal_dict("INFORM", "LOW")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] in ("QUEUE", "IGNORE")
        assert data["is_blocking"] is False

    def test_evaluate_escalate(self, client):
        resp = client.post(
            "/gravity/evaluate",
            json={"signal": self._signal_dict("ESCALATE", "HIGH")},
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "ESCALATE"

    def test_evaluate_with_context_flags(self, client):
        resp = client.post(
            "/gravity/evaluate",
            json={
                "signal": self._signal_dict("INTERRUPT", "HIGH"),
                "has_active_checkpoint": True,
                "source_trust": 1.0,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["requires_checkpoint"] is True

    def test_evaluate_invalid_signal(self, client):
        resp = client.post("/gravity/evaluate", json={"signal": {"type": "BOGUS"}})
        assert resp.status_code == 422
