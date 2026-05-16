"""PolicyClient — query and interact with the governance policy."""

from __future__ import annotations

from typing import Any

from corpus_sdk.transport import BaseTransport


class PolicyEvalResult:
    def __init__(self, data: dict[str, Any]) -> None:
        self.authorized: bool = data["authorized"]
        self.mode: str = data["mode"]
        self.reason: str = data["reason"]
        self.action_taken: str = data["action_taken"]
        self.matched_rule: str | None = data.get("matched_rule")
        self.evidence: list[str] = data.get("evidence", [])

    def __repr__(self) -> str:
        return f"PolicyEvalResult(authorized={self.authorized}, action={self.action_taken})"


class PolicyClient:
    def __init__(self, transport: BaseTransport) -> None:
        self._transport = transport

    def get(self) -> dict[str, Any]:
        return self._transport.get("/policy")

    def evaluate(
        self,
        source_product: str,
        target_product: str,
        signal_type: str,
        severity: str,
    ) -> PolicyEvalResult:
        resp = self._transport.post(
            "/policy/evaluate",
            {
                "source_product": source_product,
                "target_product": target_product,
                "signal_type": signal_type,
                "severity": severity,
            },
        )
        return PolicyEvalResult(resp)

    def reload(self) -> dict[str, Any]:
        return self._transport.post("/policy/reload", {})
