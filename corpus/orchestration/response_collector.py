"""ResponseCollector — receives product responses to orchestration tasks."""

from __future__ import annotations

from datetime import datetime, timezone

from corpus.orchestration.orchestration_models import OrchestrationTask, TaskStatus


class ResponseCollector:
    """
    Collects responses keyed by orchestration_task_id.

    Products respond by emitting signals with orchestration_task_id in their payload.
    The SignalService routes those signals here via EventBus subscriptions.
    """

    def __init__(self) -> None:
        # task_id → response dict
        self._pending: dict[str, OrchestrationTask] = {}
        self._responses: dict[str, dict] = {}

    def register(self, task: OrchestrationTask) -> None:
        self._pending[task.id] = task

    def collect(self, task_id: str, response: dict) -> None:
        """Record a response for a task. Called from EventBus handler."""
        self._responses[task_id] = response
        if task_id in self._pending:
            task = self._pending[task_id]
            task.status = TaskStatus.RESPONDED
            task.response = response
            task.responded_at = datetime.now(timezone.utc).isoformat()

    def mark_timeout(self, task: OrchestrationTask) -> None:
        if task.status == TaskStatus.DISPATCHED:
            task.status = TaskStatus.TIMEOUT

    def finalize(self, tasks: list[OrchestrationTask]) -> list[OrchestrationTask]:
        """Mark all non-responded dispatched tasks as TIMEOUT."""
        for task in tasks:
            if task.status == TaskStatus.DISPATCHED:
                self.mark_timeout(task)
        return tasks

    def clear(self, task_ids: list[str]) -> None:
        for tid in task_ids:
            self._pending.pop(tid, None)
            self._responses.pop(tid, None)
