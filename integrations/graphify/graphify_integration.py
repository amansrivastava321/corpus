"""Graphify/Nexus integration — code graph and dependency impact analysis."""

from __future__ import annotations


class GraphifyCorpusIntegration:
    """
    Graphify integration adapter.

    Capabilities: code_graph, impact_analysis
    Responds to orchestration VALIDATE requests with dependency impact.
    """

    CAPABILITIES = ["code_graph", "impact_analysis"]

    def __init__(self, corpus_url: str = "http://localhost:8000") -> None:
        from corpus_sdk import CorpusClient
        self._client = CorpusClient(
            product_name="Graphify",
            base_url=corpus_url,
        )
        self._connected = False

    def connect(self) -> None:
        self._client.connect()
        # Register capabilities with Corpus product graph
        self._connected = True

    def report_impact(
        self,
        module: str,
        affected_modules: list[str],
        risk_level: str,
        target: str = "anvil",
    ) -> dict:
        if not self._connected:
            raise RuntimeError("Call connect() first")
        return self._client.consult(
            target=target,
            message=f"Impact analysis for {module}: {len(affected_modules)} modules affected",
            payload={
                "module": module,
                "affected_modules": affected_modules,
                "risk_level": risk_level,
                "capability": "impact_analysis",
            },
        )

    def share_dependency_graph(self, graph_data: dict) -> dict:
        if not self._connected:
            raise RuntimeError("Call connect() first")
        return self._client.learn(
            target="*",
            message="Dependency graph updated",
            payload={"capability": "code_graph", "graph": graph_data},
            broadcast=True,
        )

    def disconnect(self) -> None:
        if self._connected:
            self._client.disconnect()
            self._connected = False
