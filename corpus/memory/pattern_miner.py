"""PatternMiner — detects recurring signal/decision patterns across episodes."""

from __future__ import annotations

from collections import Counter


class PatternMiner:
    """
    Mines recurring (source, target, signal_type, outcome) tuples from episodes
    and returns structured pattern records for storage.
    """

    def mine(self, episodes: list[dict], min_occurrences: int = 2) -> list[dict]:
        counter: Counter = Counter()
        for ep in episodes:
            key = (
                ep.get("source_product", ""),
                ep.get("target_product", ""),
                ep.get("signal_type", ""),
                ep.get("outcome", ""),
            )
            counter[key] += 1

        patterns = []
        for (source, target, sig_type, outcome), count in counter.items():
            if count >= min_occurrences:
                patterns.append({
                    "pattern_type": "RECURRING_SIGNAL_OUTCOME",
                    "source_product": source,
                    "target_product": target,
                    "signal_type": sig_type,
                    "outcome": outcome,
                    "occurrence_count": count,
                    "description": (
                        f"{source} → {target} via {sig_type} repeatedly results in '{outcome}'"
                    ),
                })

        # Also mine gravity-action patterns
        gravity_counter: Counter = Counter()
        for ep in episodes:
            gravity = ep.get("gravity_action")
            if gravity and ep.get("signal_type"):
                gravity_counter[(ep["signal_type"], gravity)] += 1

        for (sig_type, action), count in gravity_counter.items():
            if count >= min_occurrences:
                patterns.append({
                    "pattern_type": "GRAVITY_ACTION_PATTERN",
                    "signal_type": sig_type,
                    "gravity_action": action,
                    "occurrence_count": count,
                    "description": f"Signal type {sig_type} consistently gets gravity action {action}",
                })

        return patterns
