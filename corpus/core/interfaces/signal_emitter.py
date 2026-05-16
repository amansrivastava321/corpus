from typing import Protocol

from corpus.schemas import Signal


class SignalEmitter(Protocol):
    """Any object that can emit a signal into the Corpus runtime."""

    async def emit(self, signal: Signal) -> Signal: ...
