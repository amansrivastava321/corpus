"""SDK-level exceptions — isolated from corpus server internals."""


class CorpusSDKError(Exception):
    """Base class for all SDK errors."""


class CorpusConnectionError(CorpusSDKError):
    """Cannot reach the Corpus daemon."""


class CorpusAPIError(CorpusSDKError):
    """The daemon returned an error response."""

    def __init__(self, status_code: int, message: str, error_code: str = "unknown") -> None:
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.message = message
        self.error_code = error_code


class ProductAlreadyRegisteredError(CorpusAPIError):
    """409 — product with this name already registered."""


class ProductNotFoundError(CorpusAPIError):
    """404 — product not found."""


class SignalNotFoundError(CorpusAPIError):
    """404 — signal not found."""


class SignalExpiredError(CorpusAPIError):
    """410 — signal has expired."""


class SignalRoutingError(CorpusAPIError):
    """422 — signal could not be routed (unknown target, etc.)."""


class SignalAcknowledgementError(CorpusAPIError):
    """422 — signal acknowledgement failed."""


class NotConnectedError(CorpusSDKError):
    """Client has not called connect() yet."""
