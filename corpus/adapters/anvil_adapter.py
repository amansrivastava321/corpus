"""
Anvil adapter — reference integration for the Anvil AI development platform.

Demonstrates how an execution-heavy product integrates with Corpus:
- notifies Corpus when it starts analysing or executing
- consults Inspectra before risky code changes
- requests formal audits via VALIDATE signals
- listens for INTERRUPT and BLOCK signals before proceeding
"""

from __future__ import annotations

from typing import Any

from corpus_sdk.client import CorpusClient
from corpus_sdk.models import EmittedSignal, ReceivedSignal
from corpus_sdk.transport import BaseTransport

from corpus.adapters.base import CorpusAdapter


class AnvilAdapter(CorpusAdapter):
    """
    Reference adapter for Anvil — AI development orchestration platform.

    Anvil registers as a product that can be interrupted (BE_INTERRUPTED) and
    can emit signals to request audits or consult security tools.
    """

    DEFAULT_NAME = "Anvil"
    DEFAULT_VERSION = "0.9.0"
    DEFAULT_CAPABILITIES = [
        "EMIT_SIGNALS",
        "RECEIVE_SIGNALS",
        "BE_INTERRUPTED",
        "VALIDATE",
    ]

    @classmethod
    def from_url(cls, corpus_url: str = "http://localhost:8000") -> "AnvilAdapter":
        return cls(corpus_url=corpus_url)

    @classmethod
    def from_transport(cls, transport: BaseTransport) -> "AnvilAdapter":
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

    def notify_analysis_start(
        self, module: str, files: list[str], target: str = "Inspectra"
    ) -> EmittedSignal:
        """Tell Inspectra (or all products) that Anvil is starting to analyse a module."""
        return self.emit(
            signal_type="INFORM",
            severity="LOW",
            target=target,
            payload={"action": "analysis_started", "module": module, "files": files},
        )

    def request_audit(
        self,
        module: str,
        files: list[str],
        target: str = "Inspectra",
        pr_id: str | None = None,
    ) -> EmittedSignal:
        """Request a formal security/quality audit from Inspectra before committing."""
        return self.emit(
            signal_type="VALIDATE",
            severity="MEDIUM",
            target=target,
            payload={"module": module, "files": files, "pr_id": pr_id},
            requires_ack=True,
        )

    def consult_on_change(
        self,
        question: str,
        context: dict[str, Any],
        target: str = "Inspectra",
    ) -> EmittedSignal:
        """Ask Inspectra for advice before making a potentially risky code change."""
        return self._client.consult(target, question, context)

    def broadcast_execution_start(
        self, task: str, context: dict[str, Any] | None = None
    ) -> EmittedSignal:
        """Broadcast to all products that Anvil is starting a task."""
        return self.emit(
            signal_type="INFORM",
            severity="LOW",
            broadcast=True,
            payload={"action": "execution_started", "task": task, "context": context or {}},
        )

    def notify_execution_complete(
        self, task: str, result_summary: str, target: str = "Inspectra"
    ) -> EmittedSignal:
        return self.emit(
            signal_type="INFORM",
            severity="LOW",
            target=target,
            payload={"action": "execution_complete", "task": task, "summary": result_summary},
        )

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def handle_signal(self, signal: ReceivedSignal) -> None:
        """Log and route incoming signals by type."""
        sig_type = signal.signal_type
        if sig_type == "BLOCK":
            self._on_block(signal)
        elif sig_type == "INTERRUPT":
            self._on_interrupt(signal)
        elif sig_type == "INFORM":
            pass  # passive — no action needed
        # Subclasses override to add real handling

    def _on_block(self, signal: ReceivedSignal) -> None:
        """Called when Anvil receives a BLOCK signal. Override to halt execution."""

    def _on_interrupt(self, signal: ReceivedSignal) -> None:
        """Called when Anvil receives an INTERRUPT signal. Override to pause execution."""
