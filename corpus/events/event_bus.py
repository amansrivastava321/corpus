"""Lightweight internal event bus for Corpus runtime hooks."""

import asyncio
import logging
from collections import defaultdict
from typing import Callable

from corpus.events.event_types import CorpusEvent

_log = logging.getLogger(__name__)


class EventBus:
    """
    Publish-subscribe bus for internal Corpus events.

    Handlers may be sync or async. A failing handler is logged and skipped —
    it must never crash the main signal flow.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        self._handlers[event_type] = [
            h for h in self._handlers[event_type] if h is not handler
        ]

    async def publish(self, event: CorpusEvent) -> None:
        for handler in list(self._handlers.get(event.event_type, [])):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as exc:
                _log.warning(
                    "event_handler_error",
                    extra={"event_type": event.event_type, "error": str(exc)},
                )
