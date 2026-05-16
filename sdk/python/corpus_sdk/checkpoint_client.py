"""
CheckpointClient — SDK interface for the Corpus interrupt / governance system.

Quick start:

    client = CorpusClient(product_name="anvil")
    client.connect()

    cp = client.checkpoints().register("PRE_DEPLOY", context={"target": "prod"})
    decision = client.checkpoints().await_clearance(cp.id)

    if decision.allows_continuation:
        deploy()
        client.checkpoints().resolve(cp.id)
    else:
        client.checkpoints().cancel(cp.id)
"""

from __future__ import annotations

import time
from typing import Any

from corpus_sdk.checkpoint_models import CheckpointInfo, DecisionInfo
from corpus_sdk.transport import BaseTransport


class CheckpointClient:
    """
    Application-layer client for Corpus checkpoint governance.

    Not instantiated directly — obtained via ``CorpusClient.checkpoints()``.
    """

    def __init__(self, transport: BaseTransport) -> None:
        self._transport = transport

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(
        self,
        checkpoint_type: str,
        product_id: str,
        context: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
        timeout_policy: str = "FAIL_OPEN",
    ) -> CheckpointInfo:
        """Register a new checkpoint with Corpus.

        Args:
            checkpoint_type:  Free-form label (e.g. "PRE_DEPLOY", "CODE_REVIEW").
            product_id:       ID of the product registering the checkpoint.
            context:          Arbitrary context dict stored with the checkpoint.
            timeout_seconds:  If set, checkpoint expires after this many seconds.
            timeout_policy:   FAIL_OPEN (default) | FAIL_CLOSED | ESCALATE.
        Returns:
            CheckpointInfo with status REGISTERED.
        """
        body: dict[str, Any] = {
            "product_id": product_id,
            "checkpoint_type": checkpoint_type,
            "context": context or {},
            "timeout_policy": timeout_policy,
        }
        if timeout_seconds is not None:
            body["timeout_seconds"] = timeout_seconds

        data = self._transport.post("/checkpoints/register", json=body)
        return CheckpointInfo.from_dict(data)

    def request_clearance(self, checkpoint_id: str) -> DecisionInfo:
        """Request a clearance decision for a checkpoint.

        Moves the checkpoint into WAITING_CLEARANCE and immediately evaluates
        it against active signals. Returns the decision.
        """
        data = self._transport.post(f"/checkpoints/{checkpoint_id}/request-clearance")
        return DecisionInfo.from_dict(data)

    def resolve(self, checkpoint_id: str) -> CheckpointInfo:
        """Mark execution as successfully completed at this checkpoint."""
        data = self._transport.post(f"/checkpoints/{checkpoint_id}/resolve")
        return CheckpointInfo.from_dict(data)

    def cancel(self, checkpoint_id: str) -> CheckpointInfo:
        """Cancel this checkpoint — product chose not to proceed."""
        data = self._transport.post(f"/checkpoints/{checkpoint_id}/cancel")
        return CheckpointInfo.from_dict(data)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, checkpoint_id: str) -> CheckpointInfo:
        """Fetch the current state of a checkpoint."""
        data = self._transport.get(f"/checkpoints/{checkpoint_id}")
        return CheckpointInfo.from_dict(data)

    def get_decision(self, checkpoint_id: str) -> DecisionInfo | None:
        """Return the latest clearance decision, or None if not yet decided."""
        try:
            data = self._transport.get(f"/checkpoints/{checkpoint_id}/decision")
            if isinstance(data, dict) and data.get("error") == "not_found":
                return None
            return DecisionInfo.from_dict(data)
        except Exception:
            return None

    def list_all(
        self,
        product_id: str | None = None,
        status: str | None = None,
    ) -> list[CheckpointInfo]:
        """List checkpoints, optionally filtered by product or status."""
        params: list[str] = []
        if product_id:
            params.append(f"product_id={product_id}")
        if status:
            params.append(f"status={status}")
        qs = ("?" + "&".join(params)) if params else ""
        data = self._transport.get(f"/checkpoints{qs}")
        return [CheckpointInfo.from_dict(d) for d in (data or [])]

    def get_history(self, checkpoint_id: str) -> list[dict[str, Any]]:
        """Return the full audit trail for a checkpoint."""
        data = self._transport.get(f"/checkpoints/{checkpoint_id}/history")
        return data or []

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def await_clearance(
        self,
        checkpoint_id: str,
        poll_interval: float = 1.0,
        max_wait: float = 60.0,
    ) -> DecisionInfo:
        """Request clearance and poll until a terminal decision is reached.

        Suitable for synchronous agents that pause before proceeding.

        Args:
            checkpoint_id:  The checkpoint to evaluate.
            poll_interval:  Seconds between status polls.
            max_wait:       Maximum seconds to wait before raising TimeoutError.
        Returns:
            DecisionInfo once the decision is determined.
        Raises:
            TimeoutError: If max_wait is exceeded.
        """
        decision = self.request_clearance(checkpoint_id)

        # If decision is already final (non-reactive path returns immediately)
        if decision.decision_type in ("ALLOW", "WARN", "BLOCK", "ESCALATE"):
            return decision

        # DELAY / REROUTE — poll until the checkpoint resolves
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            cp = self.get(checkpoint_id)
            if cp.is_terminal or cp.is_cleared or cp.is_blocked:
                decision = self.get_decision(checkpoint_id)
                if decision is not None:
                    return decision

        raise TimeoutError(
            f"Clearance for checkpoint {checkpoint_id!r} not received within {max_wait}s"
        )

    def register_and_clear(
        self,
        checkpoint_type: str,
        product_id: str,
        context: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
        timeout_policy: str = "FAIL_OPEN",
        poll_interval: float = 1.0,
        max_wait: float = 60.0,
    ) -> tuple[CheckpointInfo, DecisionInfo]:
        """Register a checkpoint, request clearance, and wait for the decision.

        Returns:
            (CheckpointInfo, DecisionInfo) once a decision is reached.
        Raises:
            TimeoutError: If clearance is not received within max_wait.
        """
        cp = self.register(
            checkpoint_type=checkpoint_type,
            product_id=product_id,
            context=context,
            timeout_seconds=timeout_seconds,
            timeout_policy=timeout_policy,
        )
        decision = self.await_clearance(
            cp.id, poll_interval=poll_interval, max_wait=max_wait
        )
        return cp, decision
