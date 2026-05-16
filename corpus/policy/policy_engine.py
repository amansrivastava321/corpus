"""PolicyEngine — evaluates governance rules for signals and actions."""

from __future__ import annotations

import logging

from corpus.events.event_bus import EventBus
from corpus.events.event_types import CorpusEvent, CorpusEventType
from corpus.policy.authority_resolver import AuthorityResolver
from corpus.policy.governance_modes import capabilities
from corpus.policy.policy_models import (
    GovernanceMode,
    PolicyEvaluationResult,
    PolicyRule,
    TrustLevel,
)
from corpus.policy.trust_registry import TrustRegistry

_log = logging.getLogger(__name__)

_SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class PolicyEngine:
    """
    Evaluates whether a given signal action is authorized under current policy.

    In OBSERVER mode: always authorizes (records only).
    In ADVISOR mode: authorizes all except hard blocks.
    In GUARDIAN mode: applies full rule set.
    """

    def __init__(
        self,
        mode: GovernanceMode = GovernanceMode.GUARDIAN,
        trust_registry: TrustRegistry | None = None,
        rules: list[PolicyRule] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._mode = mode
        self._trust = trust_registry or TrustRegistry()
        self._rules = rules or []
        self._authority = AuthorityResolver(self._trust, mode)
        self._bus = event_bus

    @property
    def mode(self) -> GovernanceMode:
        return self._mode

    def reload(
        self,
        mode: GovernanceMode,
        trust_registry: TrustRegistry,
        rules: list[PolicyRule],
    ) -> None:
        self._mode = mode
        self._trust = trust_registry
        self._rules = rules
        self._authority = AuthorityResolver(trust_registry, mode)
        _log.info("policy_reloaded", extra={"mode": mode.value, "rules": len(rules)})

    def evaluate(
        self,
        source_product: str,
        target_product: str,
        signal_type: str,
        severity: str,
    ) -> PolicyEvaluationResult:
        caps = capabilities(self._mode)
        evidence: list[str] = [
            f"mode={self._mode.value}",
            f"trust={self._trust.get(source_product).value}",
        ]

        # OBSERVER mode: record-only, never intervene
        if self._mode == GovernanceMode.OBSERVER:
            return PolicyEvaluationResult(
                authorized=True,
                mode=self._mode,
                reason="OBSERVER mode — no intervention",
                action_taken="ALLOW",
                evidence=evidence,
            )

        # Check authority to emit this signal type
        if not self._authority.can_emit(source_product, signal_type):
            result = PolicyEvaluationResult(
                authorized=False,
                mode=self._mode,
                reason=f"{source_product} lacks authority to emit {signal_type}",
                action_taken="DENY",
                evidence=evidence,
            )
            self._emit_sync(result, source_product, target_product, signal_type)
            return result

        # ADVISOR: cannot hard-block
        if self._mode == GovernanceMode.ADVISOR and signal_type == "BLOCK":
            return PolicyEvaluationResult(
                authorized=True,
                mode=self._mode,
                reason="ADVISOR mode — BLOCK downgraded to WARN",
                action_taken="WARN",
                evidence=evidence + ["block_downgraded=true"],
            )

        # Apply named rules (first match wins)
        for rule in self._rules:
            if not self._rule_matches(rule, source_product, target_product, signal_type, severity):
                continue

            trust_ok = self._trust.numeric(source_product) >= rule.min_trust_level.numeric()
            if not trust_ok:
                result = PolicyEvaluationResult(
                    authorized=False,
                    mode=self._mode,
                    reason=f"Rule '{rule.name}': insufficient trust level",
                    matched_rule=rule.name,
                    action_taken="DENY",
                    evidence=evidence + [f"rule={rule.name}"],
                )
                self._emit_sync(result, source_product, target_product, signal_type)
                return result

            if rule.max_severity and self._severity_exceeds(severity, rule.max_severity):
                result = PolicyEvaluationResult(
                    authorized=False,
                    mode=self._mode,
                    reason=f"Rule '{rule.name}': severity {severity} exceeds max {rule.max_severity}",
                    matched_rule=rule.name,
                    action_taken="DENY",
                    evidence=evidence + [f"rule={rule.name}", f"severity={severity}"],
                )
                self._emit_sync(result, source_product, target_product, signal_type)
                return result

            return PolicyEvaluationResult(
                authorized=True,
                mode=self._mode,
                reason=f"Rule '{rule.name}' authorizes this signal",
                matched_rule=rule.name,
                action_taken="ALLOW",
                evidence=evidence + [f"rule={rule.name}"],
            )

        # No rule explicitly denied — allow by default in GUARDIAN mode
        return PolicyEvaluationResult(
            authorized=True,
            mode=self._mode,
            reason="No policy rule denied — default allow",
            action_taken="ALLOW",
            evidence=evidence + ["default=allow"],
        )

    def _rule_matches(
        self,
        rule: PolicyRule,
        source: str,
        target: str,
        signal_type: str,
        severity: str,
    ) -> bool:
        if rule.source_product and rule.source_product.lower() != source.lower():
            return False
        if rule.target_product and rule.target_product.lower() != target.lower():
            return False
        if rule.allowed_signal_types and signal_type not in rule.allowed_signal_types:
            return False
        return True

    @staticmethod
    def _severity_exceeds(actual: str, max_severity: str) -> bool:
        try:
            return _SEVERITY_ORDER.index(actual) > _SEVERITY_ORDER.index(max_severity)
        except ValueError:
            return False

    def _emit_sync(
        self,
        result: PolicyEvaluationResult,
        source: str,
        target: str,
        signal_type: str,
    ) -> None:
        if self._bus is None:
            return
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._emit_async(result, source, target, signal_type)
            )
        except RuntimeError:
            pass

    async def _emit_async(
        self,
        result: PolicyEvaluationResult,
        source: str,
        target: str,
        signal_type: str,
    ) -> None:
        event_type = (
            CorpusEventType.GOVERNANCE_ACTION_AUTHORIZED
            if result.authorized
            else CorpusEventType.GOVERNANCE_ACTION_DENIED
        )
        event = GovernanceActionEvent(
            event_type=event_type,
            source_product=source,
            target_product=target,
            signal_type=signal_type,
            action_taken=result.action_taken,
            mode=self._mode.value,
        )
        await self._bus.publish(event)


from dataclasses import dataclass


@dataclass
class GovernanceActionEvent(CorpusEvent):
    event_type: str = CorpusEventType.GOVERNANCE_ACTION_AUTHORIZED
    source_product: str = ""
    target_product: str = ""
    signal_type: str = ""
    action_taken: str = ""
    mode: str = ""
