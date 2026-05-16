"""MemoryService — application layer for episodic memory and learning."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from corpus.events.event_bus import EventBus
from corpus.events.event_types import CorpusEvent, CorpusEventType
from corpus.memory.embedding_index import EmbeddingIndex
from corpus.memory.episode_store import EpisodeStore
from corpus.memory.learning_artifacts import LearningArtifacts
from corpus.memory.pattern_miner import PatternMiner
from corpus.memory.recall_engine import RecallEngine

_log = logging.getLogger(__name__)


class MemoryService:
    """
    Creates/updates episodes, recalls past context, mines patterns,
    and writes learning artifacts.
    """

    def __init__(
        self,
        store: EpisodeStore,
        event_bus: EventBus | None = None,
        artifacts: LearningArtifacts | None = None,
    ) -> None:
        self._store = store
        self._bus = event_bus
        self._index = EmbeddingIndex()
        self._miner = PatternMiner()
        self._recall = RecallEngine(store, self._index)
        self._artifacts = artifacts or LearningArtifacts()

    async def record_signal_episode(
        self,
        *,
        signal_id: str,
        signal_type: str,
        severity: str,
        source_product: str,
        target_product: str,
        payload: dict,
        gravity_score: float | None = None,
        gravity_action: str | None = None,
        translation_method: str | None = None,
        policy_mode: str | None = None,
        clearance_decision: str | None = None,
        outcome: str = "PENDING",
        learning_notes: str = "",
    ) -> str:
        episode = {
            "id": str(uuid.uuid4()),
            "signal_id": signal_id,
            "signal_type": signal_type,
            "severity": severity,
            "source_product": source_product,
            "target_product": target_product,
            "payload": payload,
            "gravity_score": gravity_score,
            "gravity_action": gravity_action,
            "translation_method": translation_method,
            "policy_mode": policy_mode,
            "clearance_decision": clearance_decision,
            "outcome": outcome,
            "learning_notes": learning_notes,
            "status": "OPEN",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        episode_id = await self._store.save(episode)
        self._recall.index_episode(episode)

        if self._bus:
            await self._bus.publish(EpisodeCreatedEvent(episode_id=episode_id))

        return episode_id

    async def update_outcome(
        self,
        episode_id: str,
        outcome: str,
        learning_notes: str = "",
    ) -> None:
        episode = await self._store.get(episode_id)
        if episode is None:
            return
        episode["outcome"] = outcome
        episode["status"] = "CLOSED"
        if learning_notes:
            episode["learning_notes"] = learning_notes
        await self._store.save(episode)

        if self._bus:
            await self._bus.publish(EpisodeUpdatedEvent(episode_id=episode_id, outcome=outcome))

    async def recall(
        self,
        query: str,
        source_product: str | None = None,
        target_product: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        return await self._recall.recall(query, source_product, target_product, top_k)

    async def mine_patterns(self, min_occurrences: int = 2) -> list[dict]:
        all_episodes = await self._store.list_all(limit=500)
        patterns = self._miner.mine(all_episodes, min_occurrences)
        for p in patterns:
            await self._store.save_pattern(p)
        if self._bus:
            await self._bus.publish(PatternMinedEvent(pattern_count=len(patterns)))
        return patterns

    async def snapshot_artifacts(self) -> None:
        episodes = await self._store.list_all(limit=1000)
        patterns = await self._store.list_patterns()
        self._artifacts.write_episodes(episodes)
        self._artifacts.write_patterns(patterns)
        self._artifacts.write_summary(
            episode_count=len(episodes),
            pattern_count=len(patterns),
        )

    async def get_episode(self, episode_id: str) -> dict | None:
        return await self._store.get(episode_id)

    async def list_episodes(
        self,
        product_name: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        if product_name:
            return await self._store.list_for_product(product_name, status, limit)
        return await self._store.list_all(limit)


from dataclasses import dataclass


@dataclass
class EpisodeCreatedEvent(CorpusEvent):
    event_type: str = CorpusEventType.EPISODE_CREATED
    episode_id: str = ""


@dataclass
class EpisodeUpdatedEvent(CorpusEvent):
    event_type: str = CorpusEventType.EPISODE_UPDATED
    episode_id: str = ""
    outcome: str = ""


@dataclass
class PatternMinedEvent(CorpusEvent):
    event_type: str = CorpusEventType.PATTERN_MINED
    pattern_count: int = 0
