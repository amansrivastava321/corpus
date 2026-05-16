"""Typed error hierarchy for the Corpus runtime."""


class CorpusError(Exception):
    """Base class for all Corpus errors."""


class ProductAlreadyRegisteredError(CorpusError):
    def __init__(self, product_id: str) -> None:
        super().__init__(f"Product '{product_id}' is already registered")
        self.product_id = product_id


class ProductNotFoundError(CorpusError):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"Product '{identifier}' not found")
        self.identifier = identifier


class SignalNotFoundError(CorpusError):
    def __init__(self, signal_id: str) -> None:
        super().__init__(f"Signal '{signal_id}' not found")
        self.signal_id = signal_id


class SignalRoutingError(CorpusError):
    """Raised when a signal cannot be routed to its target."""


class SignalExpiredError(CorpusError):
    def __init__(self, signal_id: str) -> None:
        super().__init__(f"Signal '{signal_id}' has already expired")
        self.signal_id = signal_id


class SignalAcknowledgementError(CorpusError):
    """Raised when a signal acknowledgement fails."""
