"""GravityRules — priority-ordered rules mapping signal attributes to gravity actions."""

from __future__ import annotations

from dataclasses import dataclass

from corpus.gravity.gravity_score import GravityAction
from corpus.schemas import SignalSeverity, SignalType


@dataclass
class GravityRule:
    priority: int
    name: str
    signal_types: frozenset[SignalType]
    severities: frozenset[SignalSeverity]
    action: GravityAction
    score_min: float
    explanation: str
    confidence: float = 0.95


_RULES: list[GravityRule] = [
    GravityRule(
        priority=1,
        name="critical_block",
        signal_types=frozenset({SignalType.BLOCK}),
        severities=frozenset({SignalSeverity.CRITICAL}),
        action=GravityAction.BLOCK,
        score_min=30.0,
        explanation="Critical BLOCK signal — immediate execution halt required",
        confidence=1.0,
    ),
    GravityRule(
        priority=2,
        name="high_block",
        signal_types=frozenset({SignalType.BLOCK}),
        severities=frozenset({SignalSeverity.HIGH}),
        action=GravityAction.BLOCK,
        score_min=15.0,
        explanation="High-severity BLOCK signal — execution halted pending review",
        confidence=0.97,
    ),
    GravityRule(
        priority=3,
        name="escalate_any",
        signal_types=frozenset({SignalType.ESCALATE}),
        severities=frozenset({SignalSeverity.LOW, SignalSeverity.MEDIUM, SignalSeverity.HIGH, SignalSeverity.CRITICAL}),
        action=GravityAction.ESCALATE,
        score_min=12.5,
        explanation="ESCALATE signal — human review required",
        confidence=0.98,
    ),
    GravityRule(
        priority=4,
        name="critical_interrupt",
        signal_types=frozenset({SignalType.INTERRUPT}),
        severities=frozenset({SignalSeverity.CRITICAL}),
        action=GravityAction.BLOCK,
        score_min=20.0,
        explanation="Critical INTERRUPT — treating as hard block",
        confidence=0.95,
    ),
    GravityRule(
        priority=5,
        name="high_interrupt",
        signal_types=frozenset({SignalType.INTERRUPT}),
        severities=frozenset({SignalSeverity.HIGH}),
        action=GravityAction.DELAY,
        score_min=10.0,
        explanation="High-severity INTERRUPT — pause and retry",
        confidence=0.90,
    ),
    GravityRule(
        priority=6,
        name="medium_interrupt",
        signal_types=frozenset({SignalType.INTERRUPT}),
        severities=frozenset({SignalSeverity.MEDIUM}),
        action=GravityAction.DELAY,
        score_min=5.0,
        explanation="Medium INTERRUPT — delay recommended",
        confidence=0.85,
    ),
    GravityRule(
        priority=7,
        name="critical_validate",
        signal_types=frozenset({SignalType.VALIDATE}),
        severities=frozenset({SignalSeverity.CRITICAL}),
        action=GravityAction.REROUTE,
        score_min=15.0,
        explanation="Critical validation request — reroute through audit path",
        confidence=0.88,
    ),
    GravityRule(
        priority=8,
        name="high_validate",
        signal_types=frozenset({SignalType.VALIDATE}),
        severities=frozenset({SignalSeverity.HIGH}),
        action=GravityAction.WARN,
        score_min=7.5,
        explanation="High-severity validation request — proceed with caution",
        confidence=0.82,
    ),
    GravityRule(
        priority=9,
        name="medium_validate_or_consult",
        signal_types=frozenset({SignalType.VALIDATE, SignalType.CONSULT}),
        severities=frozenset({SignalSeverity.MEDIUM, SignalSeverity.HIGH}),
        action=GravityAction.WARN,
        score_min=3.0,
        explanation="Validation or consultation — warn the target",
        confidence=0.75,
    ),
    GravityRule(
        priority=10,
        name="low_block_medium",
        signal_types=frozenset({SignalType.BLOCK}),
        severities=frozenset({SignalSeverity.MEDIUM}),
        action=GravityAction.DELAY,
        score_min=7.5,
        explanation="Medium BLOCK signal — delay execution",
        confidence=0.80,
    ),
    GravityRule(
        priority=11,
        name="inform_learn",
        signal_types=frozenset({SignalType.INFORM, SignalType.LEARN}),
        severities=frozenset({SignalSeverity.LOW, SignalSeverity.MEDIUM}),
        action=GravityAction.QUEUE,
        score_min=0.0,
        explanation="Informational or learning signal — queue for async processing",
        confidence=0.70,
    ),
]

GRAVITY_RULES: list[GravityRule] = sorted(_RULES, key=lambda r: r.priority)


def apply_rules(
    signal_type: SignalType,
    severity: SignalSeverity,
    gravity_weight: float,
) -> GravityRule | None:
    for rule in GRAVITY_RULES:
        if signal_type in rule.signal_types and severity in rule.severities:
            return rule
    return None
