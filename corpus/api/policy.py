"""Policy API — query and reload the governance policy."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/policy", tags=["policy"])


class PolicyEvaluateRequest(BaseModel):
    source_product: str
    target_product: str
    signal_type: str
    severity: str


@router.get("")
async def get_policy(request: Request) -> dict:
    container = request.app.state.container
    engine = container.policy_engine
    return {
        "mode": engine.mode.value,
        "trust": engine._trust.as_dict(),
        "rule_count": len(engine._rules),
        "rules": [
            {
                "name": r.name,
                "source_product": r.source_product,
                "target_product": r.target_product,
                "allowed_signal_types": r.allowed_signal_types,
                "min_trust_level": r.min_trust_level.value,
                "description": r.description,
            }
            for r in engine._rules
        ],
    }


@router.post("/reload")
async def reload_policy(request: Request) -> dict:
    container = request.app.state.container
    from corpus.policy.policy_loader import PolicyLoader
    loader = PolicyLoader()
    mode, trust, rules = loader.default()
    container.policy_engine.reload(mode, trust, rules)
    return {"status": "ok", "mode": mode.value, "rule_count": len(rules)}


@router.post("/evaluate")
async def evaluate_policy(request_data: PolicyEvaluateRequest, request: Request) -> dict:
    container = request.app.state.container
    result = container.policy_engine.evaluate(
        source_product=request_data.source_product,
        target_product=request_data.target_product,
        signal_type=request_data.signal_type,
        severity=request_data.severity,
    )
    return {
        "authorized": result.authorized,
        "mode": result.mode.value,
        "reason": result.reason,
        "action_taken": result.action_taken,
        "matched_rule": result.matched_rule,
        "evidence": result.evidence,
    }
