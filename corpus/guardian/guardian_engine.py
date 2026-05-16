"""GuardianEngine — proactive, policy-governed intervention system."""

from __future__ import annotations

import logging

from corpus.events.event_bus import EventBus
from corpus.events.event_types import CorpusEvent, CorpusEventType
from corpus.guardian.adaptive_thresholds import AdaptiveThresholds
from corpus.guardian.guardian_models import (
    GuardianIntervention,
    GuardianMode,
    InterventionAction,
)
from corpus.guardian.guardian_state import GuardianState
from corpus.guardian.intervention_planner import InterventionPlanner
from corpus.guardian.risk_predictor import RiskPredictor
from corpus.schemas import Signal

_log = logging.getLogger(__name__)


class GuardianEngine:
    """
    Monitors live signals, predicts risk, and intervenes when policy allows.

    Rules:
    - Guardian cannot override PolicyEngine.
    - Guardian cannot make irreversible changes.
    - Guardian must explain every action.
    - Guardian supports dry-run mode.
    - Every intervention is persisted.
    """

    def __init__(
        self,
        state: GuardianState,
        event_bus: EventBus,
        mode: GuardianMode = GuardianMode.GUARDIAN,
        policy_engine=None,
        memory_service=None,
        gravity_engine=None,
        dry_run: bool = False,
    ) -> None:
        self._state = state
        self._bus = event_bus
        self._mode = mode
        self._policy = policy_engine
        self._memory = memory_service
        self._gravity = gravity_engine
        self._dry_run = dry_run
        self._predictor = RiskPredictor()
        self._planner = InterventionPlanner()
        self._thresholds = AdaptiveThresholds()

    @property
    def mode(self) -> GuardianMode:
        return self._mode

    def set_mode(self, mode: GuardianMode) -> None:
        self._mode = mode
        _log.info("guardian_mode_changed", extra={"mode": mode.value})

    async def evaluate(
        self,
        signal: Signal,
        gravity_action: str = "ALLOW",
    ) -> GuardianIntervention:
        # Recall memory for historical context
        memory_block_count = 0
        if self._memory:
            try:
                episodes = await self._memory.recall(
                    query=f"{signal.type.value} {signal.source_product}",
                    source_product=signal.source_product,
                    target_product=signal.target_product,
                )
                memory_block_count = sum(
                    1 for ep in episodes if ep.get("outcome") in ("BLOCKED", "ESCALATED")
                )
            except Exception:
                pass

        prediction = self._predictor.predict(signal, gravity_action, memory_block_count)

        # Policy authorization
        policy_authorized = True
        if self._policy and prediction.predicted_action in (
            InterventionAction.BLOCK,
            InterventionAction.REROUTE,
            InterventionAction.ESCALATE,
        ):
            result = self._policy.evaluate(
                source_product="corpus_guardian",
                target_product=signal.target_product or "",
                signal_type=signal.type.value,
                severity=signal.severity.value,
            )
            policy_authorized = result.authorized

        action, reason = self._planner.plan(
            prediction=prediction,
            mode=self._mode,
            policy_authorized=policy_authorized,
            dry_run=self._dry_run,
        )

        intervention = GuardianIntervention(
            signal_id=signal.id,
            signal_type=signal.type.value,
            source_product=signal.source_product,
            target_product=signal.target_product or "",
            action=action,
            reason=reason,
            risk_score=prediction.risk_score,
            approved_by_policy=policy_authorized,
            dry_run=self._dry_run,
        )

        await self._state.save_intervention(intervention)
        await self._bus.publish(GuardianInterventionEvent(
            intervention_id=intervention.id,
            action=action.value,
            signal_id=signal.id,
            dry_run=self._dry_run,
        ))

        _log.info(
            "guardian_intervention",
            extra={
                "action": action.value,
                "risk_score": prediction.risk_score,
                "dry_run": self._dry_run,
            },
        )
        return intervention

    async def get_status(self) -> dict:
        recent = await self._state.list_interventions(limit=10)
        return {
            "mode": self._mode.value,
            "dry_run": self._dry_run,
            "block_threshold": self._thresholds.block_threshold,
            "warn_threshold": self._thresholds.warn_threshold,
            "false_positive_rate": self._thresholds.false_positive_rate,
            "recent_interventions": len(recent),
        }

    def mark_false_positive(self) -> None:
        self._thresholds.mark_false_positive()

    def mark_true_positive(self) -> None:
        self._thresholds.mark_true_positive()


from dataclasses import dataclass


@dataclass
class GuardianInterventionEvent(CorpusEvent):
    event_type: str = CorpusEventType.GUARDIAN_INTERVENTION
    intervention_id: str = ""
    action: str = ""
    signal_id: str = ""
    dry_run: bool = False
