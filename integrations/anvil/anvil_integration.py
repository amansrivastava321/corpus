"""Anvil integration adapter — AI developer orchestration tool."""

from __future__ import annotations

from typing import Any


class AnvilCorpusIntegration:
    """
    Anvil-specific adapter for Corpus.

    Anvil emits development lifecycle signals (start task, deploy, test run)
    and registers pre-execution checkpoints for risky operations.
    """

    def __init__(self, corpus_url: str = "http://localhost:8000") -> None:
        from corpus_sdk import CorpusClient
        self._client = CorpusClient(product_name="Anvil", base_url=corpus_url)
        self._connected = False

    def connect(self) -> None:
        self._client.connect()
        self._connected = True

    def _check_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Call connect() first")

    def task_started(self, task_name: str, module: str, context: dict | None = None) -> dict:
        self._check_connected()
        return self._client.inform(
            target="*",
            message=f"Task started: {task_name}",
            payload={"task_name": task_name, "module": module, **(context or {})},
            broadcast=True,
        )

    def request_pre_deploy_clearance(
        self,
        target: str,
        commit: str,
        timeout_seconds: int = 60,
        policy: str = "FAIL_OPEN",
    ) -> tuple:
        self._check_connected()
        cp_client = self._client.checkpoints()
        return cp_client.register_and_clear(
            checkpoint_type="PRE_DEPLOY",
            product_id=self._client.product_id,
            context={"target": target, "commit": commit},
            timeout_seconds=timeout_seconds,
            timeout_policy=policy,
        )

    def signal_audit_request(self, file_paths: list[str], reason: str) -> dict:
        self._check_connected()
        return self._client.validate(
            target="inspectra",
            message=f"Audit requested: {reason}",
            payload={"files": file_paths, "reason": reason},
        )

    def evaluate_gravity(self, signal_dict: dict) -> dict:
        self._check_connected()
        g = self._client.gravity()
        result = g.evaluate(signal_dict)
        return {"score": result.score, "action": result.action, "blocking": result.is_blocking}

    def disconnect(self) -> None:
        if self._connected:
            self._client.disconnect()
            self._connected = False
