"""Generic webhook integration — maps external POST events to Corpus signals."""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


_DEFAULT_SIGNAL_MAP = {
    "push": ("INFORM", "LOW"),
    "pull_request": ("VALIDATE", "MEDIUM"),
    "deployment": ("VALIDATE", "HIGH"),
    "deployment_status.failure": ("BLOCK", "CRITICAL"),
    "security_advisory": ("ESCALATE", "CRITICAL"),
    "workflow_run.failure": ("BLOCK", "HIGH"),
}


class WebhookCorpusIntegration:
    """
    Receives external webhook events and maps them to Corpus signals.

    Usage:
        integration = WebhookCorpusIntegration(corpus_url="http://localhost:8000")
        integration.connect()
        signal = integration.handle_event("deployment_status.failure", payload)
    """

    def __init__(
        self,
        corpus_url: str = "http://localhost:8000",
        source_product: str = "webhook",
        signal_map: dict | None = None,
    ) -> None:
        from corpus_sdk import CorpusClient
        self._client = CorpusClient(product_name=source_product, base_url=corpus_url)
        self._signal_map = signal_map or _DEFAULT_SIGNAL_MAP
        self._connected = False

    def connect(self) -> None:
        self._client.connect()
        self._connected = True

    def handle_event(
        self,
        event_type: str,
        payload: dict,
        target_product: str = "*",
    ) -> dict | None:
        if not self._connected:
            raise RuntimeError("Call connect() first")

        mapping = self._signal_map.get(event_type)
        if mapping is None:
            _log.debug("webhook_unmapped_event", extra={"event_type": event_type})
            return None

        signal_type, severity = mapping
        method = getattr(self._client, signal_type.lower(), None)
        if method is None:
            return None

        return method(
            target=target_product,
            message=f"Webhook event: {event_type}",
            payload={"event_type": event_type, **payload},
        )

    def add_mapping(self, event_type: str, signal_type: str, severity: str) -> None:
        self._signal_map[event_type] = (signal_type, severity)

    def disconnect(self) -> None:
        if self._connected:
            self._client.disconnect()
            self._connected = False
