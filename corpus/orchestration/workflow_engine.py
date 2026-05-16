"""WorkflowEngine — orchestrates multi-product coordination workflows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from corpus.events.event_bus import EventBus
from corpus.events.event_types import CorpusEvent, CorpusEventType
from corpus.orchestration.coordination_plan import CoordinationPlan
from corpus.orchestration.orchestration_models import (
    OrchestrationTask,
    OrchestrationWorkflow,
    SynthesisDecision,
    SynthesizedDecision,
    TaskStatus,
    WorkflowStatus,
)
from corpus.orchestration.orchestration_state import OrchestrationState
from corpus.orchestration.product_graph import ProductGraph
from corpus.orchestration.response_collector import ResponseCollector
from corpus.orchestration.synthesis_engine import SynthesisEngine
from corpus.orchestration.task_router import TaskRouter

_log = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Coordinates multi-product workflows:
    1. Build coordination plan (which products to consult)
    2. Dispatch tasks (emit signals to target products)
    3. Collect responses (from product signal replies)
    4. Synthesize decision (gravity + policy + responses)
    5. Persist workflow state
    """

    def __init__(
        self,
        state: OrchestrationState,
        graph: ProductGraph,
        synthesis_engine: SynthesisEngine,
        response_collector: ResponseCollector,
        task_router: TaskRouter | None = None,
        event_bus: EventBus | None = None,
        policy_engine=None,
        gravity_engine=None,
        memory_service=None,
    ) -> None:
        self._state = state
        self._graph = graph
        self._synth = synthesis_engine
        self._collector = response_collector
        self._router = task_router
        self._bus = event_bus
        self._policy = policy_engine
        self._gravity = gravity_engine
        self._memory = memory_service
        self._plan_builder = CoordinationPlan(graph)

    async def create_workflow(
        self,
        name: str,
        initiating_product: str,
        subject: dict,
        required_capabilities: list[str] | None = None,
        tasks: list[dict] | None = None,
    ) -> OrchestrationWorkflow:
        workflow = OrchestrationWorkflow(
            name=name,
            initiating_product=initiating_product,
            subject=subject,
        )

        if tasks:
            for t in tasks:
                workflow.tasks.append(
                    OrchestrationTask(
                        workflow_id=workflow.id,
                        target_product=t["target_product"],
                        capability_required=t.get("capability_required", "generic"),
                        payload=t.get("payload", {}),
                        timeout_seconds=t.get("timeout_seconds", 10.0),
                    )
                )
        else:
            workflow.tasks = self._plan_builder.build(
                workflow.id, subject, required_capabilities
            )
            for task in workflow.tasks:
                task.workflow_id = workflow.id

        await self._state.save(workflow)
        if self._bus:
            await self._bus.publish(WorkflowCreatedEvent(
                workflow_id=workflow.id,
                name=name,
                initiating_product=initiating_product,
            ))
        return workflow

    async def start_workflow(self, workflow_id: str) -> OrchestrationWorkflow:
        workflow = await self._state.get(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found")
        if workflow.status not in (WorkflowStatus.PENDING,):
            raise ValueError(f"Workflow {workflow_id} is not in PENDING state")

        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now(timezone.utc).isoformat()

        # Register tasks with collector
        for task in workflow.tasks:
            self._collector.register(task)

        # Dispatch tasks
        if self._router:
            for task in workflow.tasks:
                await self._router.dispatch(task, workflow.initiating_product, "")
        else:
            # No router — mark tasks as DISPATCHED immediately
            for task in workflow.tasks:
                task.status = TaskStatus.DISPATCHED
                task.dispatched_at = datetime.now(timezone.utc).isoformat()

        # Finalize (mark non-responded as TIMEOUT since we don't wait)
        self._collector.finalize(workflow.tasks)

        # Compute gravity + policy context
        gravity_action = "ALLOW"
        if self._gravity and workflow.subject.get("signal"):
            from corpus.gravity.risk_context import RiskContext
            from corpus.schemas import Signal
            try:
                sig = Signal.model_validate(workflow.subject["signal"])
                score = self._gravity.evaluate(sig, RiskContext())
                gravity_action = score.action.value
            except Exception:
                pass

        policy_authorized = True
        if self._policy:
            result = self._policy.evaluate(
                source_product=workflow.initiating_product,
                target_product="*",
                signal_type="VALIDATE",
                severity="MEDIUM",
            )
            policy_authorized = result.authorized

        memory_block_count = 0
        if self._memory:
            episodes = await self._memory.recall(
                query=workflow.name,
                source_product=workflow.initiating_product,
            )
            memory_block_count = sum(
                1 for ep in episodes if ep.get("outcome") in ("BLOCKED", "ESCALATED")
            )

        # Synthesize decision
        synthesis = self._synth.synthesize(
            tasks=workflow.tasks,
            subject=workflow.subject,
            policy_authorized=policy_authorized,
            gravity_action=gravity_action,
            memory_block_count=memory_block_count,
        )
        workflow.synthesis = synthesis
        workflow.status = WorkflowStatus.COMPLETED
        workflow.completed_at = datetime.now(timezone.utc).isoformat()

        await self._state.save(workflow)

        # Clean up collector
        self._collector.clear([t.id for t in workflow.tasks])

        if self._bus:
            await self._bus.publish(WorkflowCompletedEvent(
                workflow_id=workflow.id,
                decision=synthesis.decision.value,
            ))

        _log.info(
            "workflow_completed",
            extra={"workflow_id": workflow_id, "decision": synthesis.decision.value},
        )
        return workflow

    async def cancel_workflow(self, workflow_id: str) -> OrchestrationWorkflow:
        workflow = await self._state.get(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found")
        if workflow.status in (WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED):
            raise ValueError(f"Workflow {workflow_id} is already {workflow.status.value}")
        workflow.status = WorkflowStatus.CANCELLED
        workflow.completed_at = datetime.now(timezone.utc).isoformat()
        await self._state.save(workflow)
        if self._bus:
            await self._bus.publish(WorkflowCancelledEvent(workflow_id=workflow.id))
        return workflow

    async def get_workflow(self, workflow_id: str) -> OrchestrationWorkflow | None:
        return await self._state.get(workflow_id)

    async def list_workflows(
        self,
        initiating_product: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[OrchestrationWorkflow]:
        return await self._state.list_all(initiating_product, status, limit)

    def record_response(self, task_id: str, response: dict) -> None:
        """Called externally when a product responds to an orchestration task."""
        self._collector.collect(task_id, response)


from dataclasses import dataclass


@dataclass
class WorkflowCreatedEvent(CorpusEvent):
    event_type: str = CorpusEventType.WORKFLOW_CREATED
    workflow_id: str = ""
    name: str = ""
    initiating_product: str = ""


@dataclass
class WorkflowCompletedEvent(CorpusEvent):
    event_type: str = CorpusEventType.WORKFLOW_COMPLETED
    workflow_id: str = ""
    decision: str = ""


@dataclass
class WorkflowCancelledEvent(CorpusEvent):
    event_type: str = CorpusEventType.WORKFLOW_CANCELLED
    workflow_id: str = ""
