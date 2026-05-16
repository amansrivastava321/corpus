"""Inspectra integration adapter — autonomous audit infrastructure tool."""

from __future__ import annotations


class InspectraCorpusIntegration:
    """
    Inspectra-specific adapter for Corpus.

    Inspectra emits audit findings as BLOCK/WARN signals and responds
    to orchestration pre-audit requests.
    """

    def __init__(self, corpus_url: str = "http://localhost:8000") -> None:
        from corpus_sdk import CorpusClient
        self._client = CorpusClient(product_name="Inspectra", base_url=corpus_url)
        self._connected = False

    def connect(self) -> None:
        self._client.connect()
        self._connected = True

    def report_critical_finding(
        self,
        finding: str,
        rule_id: str,
        file_path: str,
        target_product: str = "anvil",
    ) -> dict:
        if not self._connected:
            raise RuntimeError("Call connect() first")
        return self._client.block(
            target=target_product,
            message=f"Critical security finding: {finding}",
            payload={
                "finding": finding,
                "rule": rule_id,
                "file": file_path,
                "severity": "CRITICAL",
                "recommendation": "Fix before proceeding",
            },
        )

    def report_warning(self, finding: str, file_path: str, target: str = "anvil") -> dict:
        if not self._connected:
            raise RuntimeError("Call connect() first")
        return self._client.validate(
            target=target,
            message=f"Audit warning: {finding}",
            payload={"finding": finding, "file": file_path, "severity": "HIGH"},
        )

    def share_pattern(self, pattern_name: str, description: str) -> dict:
        if not self._connected:
            raise RuntimeError("Call connect() first")
        return self._client.learn(
            target="anvil",
            message=f"Pattern discovered: {pattern_name}",
            payload={"pattern": pattern_name, "description": description},
        )

    def disconnect(self) -> None:
        if self._connected:
            self._client.disconnect()
            self._connected = False
