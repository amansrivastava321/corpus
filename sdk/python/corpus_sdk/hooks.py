"""Client-side hooks — intercept SDK operations for logging, metrics, etc."""

from typing import Callable

from corpus_sdk.models import EmittedSignal, ReceivedSignal


class HookRegistry:
    """
    Lightweight client-side hook registry.

    Usage:
        client = CorpusClient(product_name="anvil")

        @client.hooks.on_signal_emitted
        def log_emit(signal: EmittedSignal) -> None:
            print(f"Emitted {signal.signal_type} → {signal.target_product}")

        @client.hooks.on_signal_received
        def log_receive(signal: ReceivedSignal) -> None:
            print(f"Received {signal.signal_type} from {signal.source_product}")
    """

    def __init__(self) -> None:
        self._on_pre_emit: list[Callable] = []
        self._on_post_emit: list[Callable] = []
        self._on_signal_received: list[Callable] = []
        self._on_acknowledged: list[Callable] = []
        self._on_error: list[Callable] = []

    # --- Decorators ---

    def on_pre_emit(self, fn: Callable) -> Callable:
        self._on_pre_emit.append(fn)
        return fn

    def on_signal_emitted(self, fn: Callable) -> Callable:
        self._on_post_emit.append(fn)
        return fn

    def on_signal_received(self, fn: Callable) -> Callable:
        self._on_signal_received.append(fn)
        return fn

    def on_acknowledged(self, fn: Callable) -> Callable:
        self._on_acknowledged.append(fn)
        return fn

    def on_error(self, fn: Callable) -> Callable:
        self._on_error.append(fn)
        return fn

    # --- Internal fire methods ---

    def fire_pre_emit(self, payload: dict) -> None:
        for fn in self._on_pre_emit:
            try:
                fn(payload)
            except Exception:
                pass

    def fire_post_emit(self, signal: EmittedSignal) -> None:
        for fn in self._on_post_emit:
            try:
                fn(signal)
            except Exception:
                pass

    def fire_signal_received(self, signal: ReceivedSignal) -> None:
        for fn in self._on_signal_received:
            try:
                fn(signal)
            except Exception:
                pass

    def fire_acknowledged(self, signal_id: str) -> None:
        for fn in self._on_acknowledged:
            try:
                fn(signal_id)
            except Exception:
                pass

    def fire_error(self, exc: Exception) -> None:
        for fn in self._on_error:
            try:
                fn(exc)
            except Exception:
                pass
