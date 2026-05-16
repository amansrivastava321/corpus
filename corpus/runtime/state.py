from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RuntimeState:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_signals_received: int = 0
    total_products_registered: int = 0
    expired_signals_skipped: int = 0
    last_error: str | None = None

    def uptime_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "uptime_seconds": self.uptime_seconds(),
            "total_signals_received": self.total_signals_received,
            "total_products_registered": self.total_products_registered,
            "expired_signals_skipped": self.expired_signals_skipped,
            "last_error": self.last_error,
        }
