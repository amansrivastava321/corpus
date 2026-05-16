"""InterventionPlanner — converts risk predictions into authorized interventions."""

from __future__ import annotations

from corpus.guardian.guardian_models import GuardianMode, InterventionAction, RiskPrediction


class InterventionPlanner:
    """
    Maps a RiskPrediction to an authorized InterventionAction given the
    current GuardianMode and PolicyEngine result.

    Guardian cannot override policy — if policy denies, guardian observes only.
    """

    def plan(
        self,
        prediction: RiskPrediction,
        mode: GuardianMode,
        policy_authorized: bool = True,
        dry_run: bool = False,
    ) -> tuple[InterventionAction, str]:
        """Returns (action, reason)."""

        if mode == GuardianMode.OBSERVE_ONLY:
            return (
                InterventionAction.OBSERVE_ONLY,
                f"OBSERVE_ONLY mode — risk noted: {prediction.explanation}",
            )

        if not policy_authorized:
            return (
                InterventionAction.OBSERVE_ONLY,
                "PolicyEngine denied intervention — reverting to observe-only",
            )

        predicted = prediction.predicted_action

        if mode == GuardianMode.ADVISOR:
            # Advisor cannot hard-block
            if predicted in (InterventionAction.BLOCK, InterventionAction.REROUTE):
                predicted = InterventionAction.WARN
            elif predicted == InterventionAction.ESCALATE:
                predicted = InterventionAction.REQUEST_AUDIT

        # GUARDIAN mode: use predicted action as-is
        suffix = " [DRY RUN — no enforcement]" if dry_run else ""
        reason = f"{prediction.explanation}{suffix}"
        return (predicted, reason)
