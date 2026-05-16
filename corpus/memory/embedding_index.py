"""EmbeddingIndex — lightweight keyword-based recall index (no external deps)."""

from __future__ import annotations

import re
from collections import defaultdict


class EmbeddingIndex:
    """
    Inverted keyword index over episode payloads.
    Provides simple recall without requiring an embedding model.

    If an external embedding model is later wired in, this class can be swapped
    for a vector-store backed implementation behind the same interface.
    """

    def __init__(self) -> None:
        # keyword → set of episode_ids
        self._index: dict[str, set[str]] = defaultdict(set)

    def index(self, episode_id: str, text: str) -> None:
        for token in self._tokenize(text):
            self._index[token].add(episode_id)

    def search(self, query: str, top_k: int = 10) -> list[str]:
        tokens = self._tokenize(query)
        if not tokens:
            return []
        scores: dict[str, int] = defaultdict(int)
        for token in tokens:
            for episode_id in self._index.get(token, set()):
                scores[episode_id] += 1
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [ep_id for ep_id, _ in ranked[:top_k]]

    def remove(self, episode_id: str) -> None:
        for token_set in self._index.values():
            token_set.discard(episode_id)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [t.lower() for t in re.findall(r"\w+", text) if len(t) > 2]
