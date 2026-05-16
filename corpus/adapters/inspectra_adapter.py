"""
Inspectra adapter — reference integration for the Inspectra audit platform.

Demonstrates how a security/audit product integrates with Corpus:
- emits BLOCK/INTERRUPT signals on critical findings
- broadcasts learned patterns via LEARN signals
- responds to VALIDATE requests from other products
- escalates unresolved findings to human oversight
"""

from __future__ import annotations

from corpus_sdk.client import CorpusClient
from corpus_sdk.models import EmittedSignal, ReceivedSignal
from corpus_sdk.transport import BaseTransport

from corpus.adapters.base import CorpusAdapter


class InspectraAdapter(CorpusAdapter):
    """
    Reference adapter for Inspectra — autonomous software audit infrastructure.

    Inspectra registers with the INTERRUPT and AUDIT capabilities, meaning it can
    pause other products' operations and respond to audit/validate requests.
    """

    DEFAULT_NAME = "Inspectra"
    DEFAULT_VERSION = "1.2.0"
    DEFAULT_CAPABILITIES = [
        "EMIT_SIGNALS",
        "RECEIVE_SIGNALS",
        "INTERRUPT",
        "AUDIT",
        "VALIDATE",
        "LEARN",
    ]

    @classmethod
    def from_url(cls, corpus_url: str = "http://localhost:8000") -> "InspectraAdapter":
        return cls(corpus_url=corpus_url)

    @classmethod
    def from_transport(cls, transport: BaseTransport) -> "InspectraAdapter":
        client = CorpusClient(
            product_name=cls.DEFAULT_NAME,
            product_version=cls.DEFAULT_VERSION,
            capabilities=list(cls.DEFAULT_CAPABILITIES),
            transport=transport,
        )
        return cls(client=client)

    # ------------------------------------------------------------------
    # Domain-specific signal helpers
    # ------------------------------------------------------------------

    def raise_critical_finding(
        self, target: str, reason: str, evidence: dict
    ) -> EmittedSignal:
        """BLOCK the target product due to a critical security finding."""
        return self._client.block(target, reason, evidence=evidence)

    def interrupt_execution(
        self,
        target: str,
        reason: str,
        severity: str = "HIGH",
        evidence: dict | None = None,
    ) -> EmittedSignal:
        """Request the target to pause its current operation."""
        return self._client.interrupt(target, reason, severity=severity, evidence=evidence)

    def share_pattern(
        self,
        pattern: str,
        description: str,
        details: dict | None = None,
    ) -> EmittedSignal:
        """Broadcast a discovered vulnerability/code-smell pattern to all products."""
        return self._client.learn(pattern, {"description": description, **(details or {})})

    def request_validation(
        self,
        target: str,
        artifact_ref: str,
        scope: list[str] | None = None,
    ) -> EmittedSignal:
        """Ask another product to validate an artifact (e.g. a PR diff)."""
        return self._client.validate(
            target,
            {"artifact_ref": artifact_ref},
            scope=scope or ["security", "correctness"],
        )

    def escalate_unresolved(
        self, reason: str, unacked_signal_ids: list[str]
    ) -> EmittedSignal:
        """Escalate an unresolved finding to human oversight."""
        return self._client.escalate(
            reason, context={"unacked_signal_ids": unacked_signal_ids}
        )

    def audit_complete(
        self, target: str, passed: bool, findings: list[dict]
    ) -> EmittedSignal:
        """Report audit completion to the requesting product."""
        severity = "LOW" if passed else "HIGH"
        return self.emit(
            signal_type="INFORM",
            severity=severity,
            target=target,
            payload={
                "action": "audit_complete",
                "passed": passed,
                "findings": findings,
                "finding_count": len(findings),
            },
        )

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def handle_signal(self, signal: ReceivedSignal) -> None:
        """Route incoming signals to the appropriate handler."""
        sig_type = signal.signal_type
        if sig_type == "VALIDATE":
            self._on_validate_request(signal)
        elif sig_type == "CONSULT":
            self._on_consult_request(signal)
        elif sig_type == "INFORM":
            pass  # observe passively

    def _on_validate_request(self, signal: ReceivedSignal) -> None:
        """Called when another product requests Inspectra to validate an artifact.
        Override to wire up real audit logic.
        """

    def _on_consult_request(self, signal: ReceivedSignal) -> None:
        """Called when another product consults Inspectra.
        Override to wire up real advisory logic.
        """
