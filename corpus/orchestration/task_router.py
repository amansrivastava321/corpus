"""TaskRouter — dispatches orchestration tasks as Corpus signals."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from corpus.orchestration.orchestration_models import OrchestrationTask, TaskStatus

_log = logging.getLogger(__name__)


class TaskRouter:
    """
    Dispatches orchestration tasks by emitting CONSULT/VALIDATE signals
    to target products via the SignalService.
    """

    def __init__(self, signal_service) -> None:
        self._signal_service = signal_service

    async def dispatch(
        self,
        task: OrchestrationTask,
        source_product: str,
        source_product_id: str,
    ) -> OrchestrationTask:
        try:
            signal_data = await self._signal_service.emit(
                type="VALIDATE",
                severity="MEDIUM",
                source_product=source_product,
                target_product=task.target_product,
                payload={
                    **task.payload,
                    "orchestration_task_id": task.id,
                    "workflow_id": task.workflow_id,
                    "capability_required": task.capability_required,
                },
            )
            task.status = TaskStatus.DISPATCHED
            task.signal_id = signal_data.get("id") or signal_data.get("signal_id")
            task.dispatched_at = datetime.now(timezone.utc).isoformat()
            _log.debug("task_dispatched", extra={"task_id": task.id, "target": task.target_product})
        except Exception as exc:
            _log.warning("task_dispatch_failed", extra={"task_id": task.id, "error": str(exc)})
            task.status = TaskStatus.FAILED

        return task
