"""GovernanceModeConfig — behavior table for each governance mode."""

from __future__ import annotations

from dataclasses import dataclass

from corpus.policy.policy_models import GovernanceMode


@dataclass
class ModeCapabilities:
    can_block: bool
    can_delay: bool
    can_reroute: bool
    can_escalate: bool
    can_warn: bool
    records_events: bool


_MODE_CAPABILITIES: dict[GovernanceMode, ModeCapabilities] = {
    GovernanceMode.OBSERVER: ModeCapabilities(
        can_block=False,
        can_delay=False,
        can_reroute=False,
        can_escalate=False,
        can_warn=False,
        records_events=True,
    ),
    GovernanceMode.ADVISOR: ModeCapabilities(
        can_block=False,
        can_delay=True,
        can_reroute=False,
        can_escalate=True,
        can_warn=True,
        records_events=True,
    ),
    GovernanceMode.GUARDIAN: ModeCapabilities(
        can_block=True,
        can_delay=True,
        can_reroute=True,
        can_escalate=True,
        can_warn=True,
        records_events=True,
    ),
}


def capabilities(mode: GovernanceMode) -> ModeCapabilities:
    return _MODE_CAPABILITIES[mode]
