"""Structured logging utilities for the Corpus runtime."""

import structlog


def configure(*, json_logs: bool = False, level: str = "INFO") -> None:
    """Configure structlog for the Corpus daemon.

    Call once at startup (server.py does this automatically).
    """
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(processors=processors)


def get_logger(name: str = "") -> structlog.BoundLogger:  # type: ignore[type-arg]
    return structlog.get_logger(name)


def bind(**kwargs) -> None:
    """Bind key-value pairs to the current async context (request-scoped tracing)."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear() -> None:
    structlog.contextvars.clear_contextvars()
