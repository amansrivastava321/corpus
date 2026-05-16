"""Phase 10 — Guardian Mode tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from corpus.guardian.adaptive_thresholds import AdaptiveThresholds
from corpus.guardian.guardian_models import GuardianMode, InterventionAction
from corpus.guardian.intervention_planner import InterventionPlanner
from corpus.guardian.risk_predictor import RiskPredictor
from corpus.schemas import Signal, SignalSeverity, SignalType
from corpus.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


def _signal_dict(sig_type: str = "BLOCK", severity: str = "CRITICAL") -> dict:
    return {
        "type": sig_type,
        "severity": severity,
        "source_product": "inspectra",
        "target_product": "anvil",
    }


def _signal(sig_type: str = "BLOCK", severity: str = "CRITICAL") -> Signal:
    return Signal(
        type=SignalType(sig_type),
        severity=SignalSeverity(severity),
        source_product="inspectra",
        target_product="anvil",
    )


# ─── Unit tests ──────────────────────────────────────────────────────────────

class TestRiskPredictor:
    def test_critical_block_high_risk(self):
        predictor = RiskPredictor()
        sig = _signal("BLOCK", "CRITICAL")
        result = predictor.predict(sig)
        assert result.risk_level in ("HIGH", "CRITICAL")
        assert result.risk_score > 0.5

    def test_inform_low_low_risk(self):
        predictor = RiskPredictor()
        sig = _signal("INFORM", "LOW")
        result = predictor.predict(sig)
        assert result.risk_level in ("LOW", "MEDIUM")
        assert result.risk_score < 0.5

    def test_memory_blocks_increase_risk(self):
        predictor = RiskPredictor()
        sig = _signal("INTERRUPT", "HIGH")
        no_mem = predictor.predict(sig, memory_block_count=0)
        with_mem = predictor.predict(sig, memory_block_count=10)
        assert with_mem.risk_score >= no_mem.risk_score

    def test_gravity_block_boosts_risk(self):
        predictor = RiskPredictor()
        sig = _signal("INTERRUPT", "MEDIUM")
        plain = predictor.predict(sig, gravity_action="ALLOW")
        boosted = predictor.predict(sig, gravity_action="BLOCK")
        assert boosted.risk_score > plain.risk_score

    def test_risk_score_in_range(self):
        predictor = RiskPredictor()
        for sig_type in SignalType:
            for severity in SignalSeverity:
                sig = _signal(sig_type.value, severity.value)
                result = predictor.predict(sig)
                assert 0.0 <= result.risk_score <= 1.0

    def test_explanation_non_empty(self):
        predictor = RiskPredictor()
        result = predictor.predict(_signal("BLOCK", "CRITICAL"))
        assert result.explanation


class TestInterventionPlanner:
    def test_observe_only_mode_never_intervenes(self):
        planner = InterventionPlanner()
        from corpus.guardian.guardian_models import RiskPrediction
        prediction = RiskPrediction(
            risk_level="CRITICAL", risk_score=0.99,
            predicted_action=InterventionAction.BLOCK,
            explanation="critical block",
        )
        action, reason = planner.plan(prediction, GuardianMode.OBSERVE_ONLY)
        assert action == InterventionAction.OBSERVE_ONLY

    def test_advisor_downgrades_block_to_warn(self):
        planner = InterventionPlanner()
        from corpus.guardian.guardian_models import RiskPrediction
        prediction = RiskPrediction(
            risk_level="HIGH", risk_score=0.85,
            predicted_action=InterventionAction.BLOCK,
            explanation="block predicted",
        )
        action, _ = planner.plan(prediction, GuardianMode.ADVISOR)
        assert action == InterventionAction.WARN

    def test_guardian_allows_block(self):
        planner = InterventionPlanner()
        from corpus.guardian.guardian_models import RiskPrediction
        prediction = RiskPrediction(
            risk_level="CRITICAL", risk_score=0.95,
            predicted_action=InterventionAction.BLOCK,
            explanation="critical",
        )
        action, _ = planner.plan(prediction, GuardianMode.GUARDIAN)
        assert action == InterventionAction.BLOCK

    def test_policy_denied_observe_only(self):
        planner = InterventionPlanner()
        from corpus.guardian.guardian_models import RiskPrediction
        prediction = RiskPrediction(
            risk_level="HIGH", risk_score=0.8,
            predicted_action=InterventionAction.BLOCK,
            explanation="test",
        )
        action, reason = planner.plan(prediction, GuardianMode.GUARDIAN, policy_authorized=False)
        assert action == InterventionAction.OBSERVE_ONLY
        assert "PolicyEngine" in reason

    def test_dry_run_appends_note(self):
        planner = InterventionPlanner()
        from corpus.guardian.guardian_models import RiskPrediction
        prediction = RiskPrediction(
            risk_level="LOW", risk_score=0.1,
            predicted_action=InterventionAction.OBSERVE_ONLY,
            explanation="low",
        )
        _, reason = planner.plan(prediction, GuardianMode.GUARDIAN, dry_run=True)
        assert "DRY RUN" in reason


class TestAdaptiveThresholds:
    def test_initial_defaults(self):
        t = AdaptiveThresholds()
        assert t.block_threshold == 0.8
        assert t.warn_threshold == 0.4

    def test_false_positives_raise_threshold(self):
        t = AdaptiveThresholds()
        original = t.block_threshold
        for _ in range(20):
            t.mark_false_positive()
        assert t.block_threshold >= original

    def test_true_positives_maintain_threshold(self):
        t = AdaptiveThresholds()
        for _ in range(10):
            t.mark_true_positive()
        assert t.false_positive_rate == 0.0


# ─── REST API tests ───────────────────────────────────────────────────────────

class TestGuardianAPI:
    def test_status_endpoint(self, client):
        resp = client.get("/guardian/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data
        assert "dry_run" in data

    def test_evaluate_critical_block(self, client):
        resp = client.post(
            "/guardian/evaluate",
            json={"signal": _signal_dict("BLOCK", "CRITICAL"), "gravity_action": "BLOCK"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "action" in data
        assert "reason" in data
        assert "risk_score" in data
        assert 0.0 <= data["risk_score"] <= 1.0

    def test_evaluate_inform_low(self, client):
        resp = client.post(
            "/guardian/evaluate",
            json={"signal": _signal_dict("INFORM", "LOW"), "gravity_action": "QUEUE"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] in [a.value for a in InterventionAction]

    def test_evaluate_invalid_signal(self, client):
        resp = client.post("/guardian/evaluate", json={"signal": {"type": "BOGUS"}})
        assert resp.status_code == 422

    def test_set_mode_observer(self, client):
        resp = client.post("/guardian/mode", json={"mode": "OBSERVE_ONLY"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "OBSERVE_ONLY"

    def test_set_mode_invalid(self, client):
        resp = client.post("/guardian/mode", json={"mode": "INVALID_MODE"})
        assert resp.status_code == 422

    def test_list_interventions_empty(self, client):
        resp = client.get("/guardian/interventions")
        assert resp.status_code == 200
        assert "interventions" in resp.json()

    def test_list_interventions_after_evaluate(self, client):
        client.post(
            "/guardian/evaluate",
            json={"signal": _signal_dict("BLOCK", "CRITICAL")},
        )
        resp = client.get("/guardian/interventions")
        assert resp.json()["count"] >= 1

    def test_get_intervention_by_id(self, client):
        eval_resp = client.post(
            "/guardian/evaluate",
            json={"signal": _signal_dict("BLOCK", "HIGH")},
        )
        iid = eval_resp.json()["id"]
        resp = client.get(f"/guardian/interventions/{iid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == iid

    def test_get_intervention_not_found(self, client):
        resp = client.get("/guardian/interventions/nonexistent")
        assert resp.status_code == 404

    def test_set_dry_run_mode(self, client):
        resp = client.post("/guardian/mode", json={"mode": "GUARDIAN", "dry_run": True})
        assert resp.status_code == 200
        assert resp.json()["dry_run"] is True
