"""RecallEngine — retrieves relevant past episodes for a given query."""

from __future__ import annotations

from corpus.memory.embedding_index import EmbeddingIndex
from corpus.memory.episode_store import EpisodeStore


class RecallEngine:
    """
    Combines keyword index lookup with EpisodeStore retrieval.
    Returns the most relevant past episodes for context enrichment.
    """

    def __init__(self, store: EpisodeStore, index: EmbeddingIndex) -> None:
        self._store = store
        self._index = index

    async def recall(
        self,
        query: str,
        source_product: str | None = None,
        target_product: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        candidate_ids = self._index.search(query, top_k=top_k * 3)
        results: list[dict] = []
        seen: set[str] = set()

        for ep_id in candidate_ids:
            if ep_id in seen:
                continue
            ep = await self._store.get(ep_id)
            if ep is None:
                continue
            if source_product and ep.get("source_product") != source_product:
                continue
            if target_product and ep.get("target_product") != target_product:
                continue
            results.append(ep)
            seen.add(ep_id)
            if len(results) >= top_k:
                break

        return results

    def index_episode(self, episode: dict) -> None:
        text_parts = [
            episode.get("signal_type", ""),
            episode.get("source_product", ""),
            episode.get("target_product", ""),
            episode.get("outcome", ""),
            str(episode.get("payload", "")),
            episode.get("learning_notes", ""),
        ]
        self._index.index(episode["id"], " ".join(text_parts))
