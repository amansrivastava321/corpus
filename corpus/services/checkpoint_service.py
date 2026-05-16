"""
CheckpointService — orchestrates the full checkpoint + clearance lifecycle.

This is the single application-layer boundary for all checkpoint operations.
Routes call in, repositories and engines are called out.

Lifecycle:
  register()          → REGISTERED
  request_clearance() → WAITING_CLEARANCE → decision → status update
  resolve()           → RESOLVED
  cancel()            → CANCELLED
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from corpus import log
from corpus.audit.audit_log import AuditLog
from corpus.checkpoints.models import (
    RuntimeCheckpoint,
    RuntimeCheckpointStatus,
    RuntimeDecision,
    RuntimeDecisionType,
    TimeoutPolicy,
)
from corpus.clearance.clearance_engine import ClearanceEngine
from corpus.errors import ProductNotFoundError
from corpus.events.event_bus import EventBus
from corpus.events.event_types import (
    CheckpointRegisteredEvent,
    ClearanceGrantedEvent,
    ExecutionBlockedEvent,
    ExecutionEscalatedEvent,
    ExecutionResumedEvent,
)
from corpus.registry.product_registry import ProductRegistry
from corpus.storage.checkpoint_repository import CheckpointRepository, DecisionRepository
from corpus.websocket.connection_manager import ConnectionManager
from corpus.websocket.message_types import WsMessage

_log = log.get_logger("corpus.checkpoint_service")


class CheckpointService:
    def __init__(
        self,
        checkpoint_repo: CheckpointRepository,
        decision_repo: DecisionRepository,
        clearance_engine: ClearanceEngine,
        registry: ProductRegistry,
        audit: AuditLog,
        event_bus: EventBus,
        connection_manager: ConnectionManager,
    ) -> None:
        self._checkpoint_repo = checkpoint_repo
        self._decision_repo = decision_repo
        self._engine = clearance_engine
        self._registry = registry
        self._audit = audit
        self._bus = event_bus
        self._conn_mgr = connection_manager

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(
        self,
        product_id: str,
        checkpoint_type: str,
        context: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
        timeout_policy: str = "FAIL_OPEN",
    ) -> RuntimeCheckpoint:
        # Validate product exists
        product = await self._registry.get_product(product_id)

        timeout_at = None
        if timeout_seconds is not None:
            timeout_at = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)

        checkpoint = RuntimeCheckpoint(
            product_id=product.product_id,
            product_name=product.name,
            checkpoint_type=checkpoint_type,
            context=context or {},
            timeout_at=timeout_at,
            timeout_policy=TimeoutPolicy(timeout_policy),
        )
        await self._checkpoint_repo.save(checkpoint)
        await self._audit.append(
            checkpoint.id,
            "REGISTERED",
            {"product_id": product.product_id, "checkpoint_type": checkpoint_type},
        )
        await self._bus.publish(
            CheckpointRegisteredEvent(
                checkpoint_id=checkpoint.id,
                product_id=product.product_id,
                checkpoint_type=checkpoint_type,
            )
        )
        _log.info(
            "checkpoint.registered",
            checkpoint_id=checkpoint.id,
            product=product.name,
            type=checkpoint_type,
        )
        return checkpoint

    # ------------------------------------------------------------------
    # Clearance
    # ------------------------------------------------------------------

    async def request_clearance(
        self,
        checkpoint_id: str,
        reactive: bool = False,
    ) -> RuntimeDecision:
        """Evaluate a checkpoint and return the clearance decision.

        Args:
            checkpoint_id: The checkpoint to evaluate.
            reactive:      If True, this call was triggered by the interrupt bridge
                           reacting to a new signal, not a direct product request.
                           In reactive mode, we only re-evaluate checkpoints that are
                           already in WAITING_CLEARANCE and only update if the new
                           decision is more severe.
        """
        checkpoint = await self._get_or_raise(checkpoint_id)

        if reactive and checkpoint.status != RuntimeCheckpointStatus.WAITING_CLEARANCE:
            # Don't reactively change terminal or not-yet-waiting checkpoints
            existing = await self._decision_repo.latest_for_checkpoint(checkpoint_id)
            if existing:
                return existing
            # Fall through to evaluate

        # Move to WAITING_CLEARANCE
        checkpoint.status = RuntimeCheckpointStatus.WAITING_CLEARANCE
        checkpoint.touch()
        await self._checkpoint_repo.update(checkpoint)
        await self._audit.append(checkpoint.id, "CLEARANCE_REQUESTED", {"reactive": reactive})

        # Check timeout before evaluating
        if checkpoint.is_expired():
            return await self._handle_timeout(checkpoint)

        # Evaluate
        decision = await self._engine.evaluate(checkpoint)
        await self._decision_repo.save(decision)

        # Update checkpoint status
        new_status = decision.decision_type.to_checkpoint_status()
        checkpoint.status = new_status
        checkpoint.decision_id = decision.id
        checkpoint.touch()
        await self._checkpoint_repo.update(checkpoint)
        await self._audit.append(
            checkpoint.id,
            "CLEARANCE_DECIDED",
            {
                "decision_type": decision.decision_type.value,
                "reason": decision.reason,
                "trigger_signal_id": decision.trigger_signal_id,
            },
        )

        # Publish events and push via WS
        await self._publish_and_push(checkpoint, decision)

        _log.info(
            "checkpoint.clearance_decided",
            checkpoint_id=checkpoint.id,
            decision=decision.decision_type.value,
            product=checkpoint.product_name,
        )
        return decision

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def resolve(self, checkpoint_id: str) -> RuntimeCheckpoint:
        """Mark a checkpoint as RESOLVED — execution completed."""
        checkpoint = await self._get_or_raise(checkpoint_id)
        checkpoint.status = RuntimeCheckpointStatus.RESOLVED
        checkpoint.resolved_at = datetime.now(timezone.utc)
        checkpoint.touch()
        await self._checkpoint_repo.update(checkpoint)
        await self._audit.append(checkpoint.id, "RESOLVED", {})
        await self._bus.publish(
            ExecutionResumedEvent(
                checkpoint_id=checkpoint.id,
                product_id=checkpoint.product_id,
            )
        )
        return checkpoint

    async def cancel(self, checkpoint_id: str) -> RuntimeCheckpoint:
        """Cancel a checkpoint — product chose not to proceed."""
        checkpoint = await self._get_or_raise(checkpoint_id)
        checkpoint.status = RuntimeCheckpointStatus.CANCELLED
        checkpoint.touch()
        await self._checkpoint_repo.update(checkpoint)
        await self._audit.append(checkpoint.id, "CANCELLED", {})
        return checkpoint

    # ------------------------------------------------------------------
    # Timeout enforcement
    # ------------------------------------------------------------------

    async def enforce_timeouts(self) -> list[str]:
        """Called by background monitor. Returns IDs of checkpoints that timed out."""
        expiring = await self._checkpoint_repo.list_expiring()
        timed_out = []
        for checkpoint in expiring:
            await self._handle_timeout(checkpoint)
            timed_out.append(checkpoint.id)
        return timed_out

    async def _handle_timeout(self, checkpoint: RuntimeCheckpoint) -> RuntimeDecision:
        policy = checkpoint.timeout_policy
        if policy == TimeoutPolicy.FAIL_OPEN:
            decision_type = RuntimeDecisionType.ALLOW
            reason = f"Checkpoint timed out — FAIL_OPEN policy applied"
        elif policy == TimeoutPolicy.FAIL_CLOSED:
            decision_type = RuntimeDecisionType.BLOCK
            reason = "Checkpoint timed out — FAIL_CLOSED policy applied"
        else:  # ESCALATE
            decision_type = RuntimeDecisionType.ESCALATE
            reason = "Checkpoint timed out — ESCALATE policy applied"

        decision = RuntimeDecision(
            checkpoint_id=checkpoint.id,
            decision_type=decision_type,
            reason=reason,
            decided_by="timeout_handler",
        )
        await self._decision_repo.save(decision)
        checkpoint.status = RuntimeCheckpointStatus.EXPIRED
        checkpoint.decision_id = decision.id
        checkpoint.touch()
        await self._checkpoint_repo.update(checkpoint)
        await self._audit.append(
            checkpoint.id,
            "TIMEOUT",
            {"policy": policy.value, "decision": decision_type.value},
        )
        await self._publish_and_push(checkpoint, decision)
        return decision

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get(self, checkpoint_id: str) -> RuntimeCheckpoint:
        return await self._get_or_raise(checkpoint_id)

    async def list_all(
        self,
        product_id: str | None = None,
        status: str | None = None,
    ) -> list[RuntimeCheckpoint]:
        return await self._checkpoint_repo.list_all(product_id=product_id, status=status)

    async def get_history(self, checkpoint_id: str) -> list[dict]:
        await self._get_or_raise(checkpoint_id)  # validate existence
        return await self._audit.get_history(checkpoint_id)

    async def get_decision(self, checkpoint_id: str) -> RuntimeDecision | None:
        await self._get_or_raise(checkpoint_id)
        return await self._decision_repo.latest_for_checkpoint(checkpoint_id)

    async def get_all_decisions(self, checkpoint_id: str) -> list[RuntimeDecision]:
        await self._get_or_raise(checkpoint_id)
        return await self._decision_repo.get_for_checkpoint(checkpoint_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_or_raise(self, checkpoint_id: str) -> RuntimeCheckpoint:
        from corpus.errors import CorpusError
        checkpoint = await self._checkpoint_repo.get(checkpoint_id)
        if checkpoint is None:
            raise CorpusError(f"Checkpoint '{checkpoint_id}' not found")
        return checkpoint

    async def _publish_and_push(
        self, checkpoint: RuntimeCheckpoint, decision: RuntimeDecision
    ) -> None:
        """Publish domain event and push clearance decision via WebSocket."""
        if decision.is_blocking():
            await self._bus.publish(
                ExecutionBlockedEvent(
                    checkpoint_id=checkpoint.id,
                    product_id=checkpoint.product_id,
                    reason=decision.reason,
                    trigger_signal_id=decision.trigger_signal_id,
                )
            )
            if decision.decision_type == RuntimeDecisionType.ESCALATE:
                await self._bus.publish(
                    ExecutionEscalatedEvent(
                        checkpoint_id=checkpoint.id,
                        product_id=checkpoint.product_id,
                        reason=decision.reason,
                    )
                )
        else:
            await self._bus.publish(
                ClearanceGrantedEvent(
                    checkpoint_id=checkpoint.id,
                    product_id=checkpoint.product_id,
                    decision_type=decision.decision_type.value,
                    decision_id=decision.id,
                )
            )

        # Push over WebSocket if product is connected
        await self._push_ws_decision(checkpoint, decision)

    async def _push_ws_decision(
        self, checkpoint: RuntimeCheckpoint, decision: RuntimeDecision
    ) -> None:
        """Send clearance decision to connected product via WebSocket."""
        if not self._conn_mgr.is_connected(checkpoint.product_id):
            return

        msg_type = (
            "EXECUTION_BLOCKED" if decision.is_blocking() else "CLEARANCE_DECISION"
        )
        if decision.decision_type == RuntimeDecisionType.ESCALATE:
            msg_type = "EXECUTION_ESCALATED"
        elif decision.decision_type == RuntimeDecisionType.ALLOW or decision.decision_type == RuntimeDecisionType.WARN:
            msg_type = "CLEARANCE_DECISION"

        await self._conn_mgr.send_raw(
            checkpoint.product_id,
            {
                "message_type": msg_type,
                "checkpoint_id": checkpoint.id,
                "checkpoint_type": checkpoint.checkpoint_type,
                "decision_type": decision.decision_type.value,
                "reason": decision.reason,
                "trigger_signal_id": decision.trigger_signal_id,
                "decided_by": decision.decided_by,
                "allows_continuation": decision.allows_continuation(),
            },
        )
