"""AdaptiveThresholds — adjusts intervention thresholds based on false-positive history."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class ThresholdConfig:
    block_threshold: float = 0.8
    warn_threshold: float = 0.4
    audit_threshold: float = 0.6
    # Exponential moving average window
    window: int = 50


class AdaptiveThresholds:
    """
    Tracks intervention outcomes and adjusts thresholds to reduce false positives.
    Each marked false_positive raises thresholds slightly; each confirmed true_positive
    lowers them.
    """

    def __init__(self, config: ThresholdConfig | None = None) -> None:
        self._cfg = config or ThresholdConfig()
        self._history: deque[bool] = deque(maxlen=self._cfg.window)

    def mark_false_positive(self) -> None:
        self._history.append(False)
        self._adjust()

    def mark_true_positive(self) -> None:
        self._history.append(True)
        self._adjust()

    def _adjust(self) -> None:
        if not self._history:
            return
        fp_rate = self._history.count(False) / len(self._history)
        # If FP rate > 30%, raise thresholds to reduce noise
        if fp_rate > 0.30:
            self._cfg.block_threshold = min(0.95, self._cfg.block_threshold + 0.01)
            self._cfg.warn_threshold = min(0.60, self._cfg.warn_threshold + 0.01)
        # If FP rate < 5%, lower thresholds to catch more risks
        elif fp_rate < 0.05 and len(self._history) >= 10:
            self._cfg.block_threshold = max(0.60, self._cfg.block_threshold - 0.01)
            self._cfg.warn_threshold = max(0.25, self._cfg.warn_threshold - 0.01)

    @property
    def block_threshold(self) -> float:
        return self._cfg.block_threshold

    @property
    def warn_threshold(self) -> float:
        return self._cfg.warn_threshold

    @property
    def false_positive_rate(self) -> float:
        if not self._history:
            return 0.0
        return self._history.count(False) / len(self._history)
