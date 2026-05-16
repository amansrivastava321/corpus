"""LearningArtifacts — writes episodes/patterns/summary to artifacts/memory/."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)

_ARTIFACTS_DIR = Path(__file__).parent.parent.parent / "artifacts" / "memory"


class LearningArtifacts:
    """Persists learning snapshots as JSON files for offline inspection."""

    def __init__(self, artifacts_dir: Path | None = None) -> None:
        self._dir = artifacts_dir or _ARTIFACTS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def write_episodes(self, episodes: list[dict]) -> None:
        self._write("episodes.json", episodes)

    def write_patterns(self, patterns: list[dict]) -> None:
        self._write("patterns.json", patterns)

    def write_summary(self, episode_count: int, pattern_count: int, extra: dict | None = None) -> None:
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "episode_count": episode_count,
            "pattern_count": pattern_count,
        }
        if extra:
            summary.update(extra)
        self._write("learning_summary.json", summary)

    def _write(self, filename: str, data: object) -> None:
        path = self._dir / filename
        try:
            path.write_text(json.dumps(data, indent=2, default=str))
        except OSError as exc:
            _log.warning("artifacts_write_failed", extra={"file": filename, "error": str(exc)})
