"""SDK configuration — loaded from kwargs or environment variables."""

import os
from dataclasses import dataclass, field


@dataclass
class CorpusConfig:
    base_url: str = "http://localhost:8000"
    timeout: float = 10.0
    retries: int = 3
    retry_delay: float = 0.5

    @classmethod
    def from_env(cls) -> "CorpusConfig":
        return cls(
            base_url=os.environ.get("CORPUS_URL", "http://localhost:8000"),
            timeout=float(os.environ.get("CORPUS_TIMEOUT", "10.0")),
            retries=int(os.environ.get("CORPUS_RETRIES", "3")),
            retry_delay=float(os.environ.get("CORPUS_RETRY_DELAY", "0.5")),
        )
