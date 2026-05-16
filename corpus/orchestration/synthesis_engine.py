"""SynthesisEngine — synthesizes a decision from task results + gravity + policy."""

from __future__ import annotations

from corpus.orchestration.orchestration_models import (
    OrchestrationTask,
    SynthesisDecision,
    SynthesizedDecision,
    TaskStatus,
)


class SynthesisEngine:
    """
    Synthesizes a final orchestration decision from:
    - task statuses and responses
    - policy evaluation result (passed in)
    - subject context (gravity, memory recall)
    """

    def synthesize(
        self,
        tasks: list[OrchestrationTask],
        subject: dict,
        policy_authorized: bool = True,
        gravity_action: str = "ALLOW",
        memory_block_count: int = 0,
    ) -> SynthesizedDecision:
        factors: list[str] = []
        blocks = 0
        warnings = 0
        timeouts = 0

        for task in tasks:
            if task.status == TaskStatus.RESPONDED and task.response:
                resp_decision = str(task.response.get("decision", "")).upper()
                if resp_decision in ("BLOCK", "ESCALATE"):
                    blocks += 1
                    factors.append(f"{task.target_product}:{task.capability_required}=BLOCK")
                elif resp_decision in ("WARN", "DELAY"):
                    warnings += 1
                    factors.append(f"{task.target_product}:{task.capability_required}=WARN")
                else:
                    factors.append(f"{task.target_product}:{task.capability_required}=ALLOW")
            elif task.status == TaskStatus.TIMEOUT:
                timeouts += 1
                factors.append(f"{task.target_product}:{task.capability_required}=TIMEOUT")
            elif task.status == TaskStatus.FAILED:
                factors.append(f"{task.target_product}:{task.capability_required}=FAILED")

        # Gravity engine result modulates decision
        if gravity_action in ("BLOCK", "ESCALATE"):
            blocks += 1
            factors.append(f"gravity={gravity_action}")
        elif gravity_action in ("DELAY", "WARN", "REROUTE"):
            warnings += 1
            factors.append(f"gravity={gravity_action}")

        # Memory-informed historical blocks
        if memory_block_count >= 3:
            warnings += 1
            factors.append(f"memory_historical_blocks={memory_block_count}")

        # Final decision
        if not policy_authorized:
            return SynthesizedDecision(
                decision=SynthesisDecision.BLOCK,
                confidence=1.0,
                reasoning="PolicyEngine denied this orchestration — insufficient authority",
                contributing_factors=factors,
                blocking_signals=blocks,
                warning_signals=warnings,
                timeout_tasks=timeouts,
            )

        if blocks > 0:
            decision = SynthesisDecision.BLOCK
            reasoning = f"{blocks} blocking signal(s) detected across consulted products"
            confidence = min(0.95, 0.7 + blocks * 0.1)
        elif gravity_action == "REROUTE":
            decision = SynthesisDecision.REROUTE
            reasoning = "Gravity engine recommends reroute through alternate path"
            confidence = 0.80
        elif warnings > 0 or timeouts > 0:
            decision = SynthesisDecision.WARN
            reasoning = (
                f"{warnings} warning(s), {timeouts} timeout(s) — proceed with caution"
            )
            confidence = max(0.5, 0.75 - timeouts * 0.05)
        else:
            decision = SynthesisDecision.ALLOW
            reasoning = "No blocking signals — orchestration cleared"
            confidence = 0.90

        return SynthesizedDecision(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            contributing_factors=factors,
            blocking_signals=blocks,
            warning_signals=warnings,
            timeout_tasks=timeouts,
        )
