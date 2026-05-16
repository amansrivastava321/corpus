"""CoordinationPlan — builds orchestration task lists from subject + product graph."""

from __future__ import annotations

from corpus.orchestration.orchestration_models import OrchestrationTask
from corpus.orchestration.product_graph import ProductGraph


class CoordinationPlan:
    """
    Derives which products to consult for a given orchestration subject.

    The plan builder inspects the subject's required capabilities and maps them
    to registered products. If no product has the capability, the task is skipped.
    """

    def __init__(self, graph: ProductGraph) -> None:
        self._graph = graph

    def build(
        self,
        workflow_id: str,
        subject: dict,
        required_capabilities: list[str] | None = None,
    ) -> list[OrchestrationTask]:
        """
        Build tasks by matching required_capabilities to registered products.

        If required_capabilities is None, build a default plan:
        - ask all VALIDATE-capable products for audit
        - ask all impact_analysis-capable products
        """
        caps = required_capabilities or self._infer_capabilities(subject)
        tasks: list[OrchestrationTask] = []
        seen: set[str] = set()

        for cap in caps:
            for node in self._graph.find_by_capability(cap):
                if node.product_id in seen:
                    continue
                tasks.append(
                    OrchestrationTask(
                        workflow_id=workflow_id,
                        target_product=node.product_name,
                        capability_required=cap,
                        payload={
                            "subject": subject,
                            "capability": cap,
                            "requested_by": "corpus_orchestration",
                        },
                    )
                )
                seen.add(node.product_id)

        return tasks

    @staticmethod
    def _infer_capabilities(subject: dict) -> list[str]:
        """Default capabilities to check for any orchestration subject."""
        caps = ["audit", "validate"]
        action = subject.get("action", "")
        if "deploy" in action.lower():
            caps += ["ci_status", "impact_analysis"]
        if "refactor" in action.lower():
            caps += ["impact_analysis", "code_graph"]
        return caps
