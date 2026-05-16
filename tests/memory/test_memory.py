"""Phase 7 — Episodic Memory & Learning tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from corpus.memory.embedding_index import EmbeddingIndex
from corpus.memory.pattern_miner import PatternMiner
from corpus.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


def _register(client: TestClient, name: str) -> dict:
    resp = client.post("/products/register", json={"name": name, "version": "1.0.0"})
    assert resp.status_code == 201
    return resp.json()


# ─── Unit tests ──────────────────────────────────────────────────────────────

class TestEmbeddingIndex:
    def test_index_and_search_returns_episode(self):
        idx = EmbeddingIndex()
        idx.index("ep-1", "critical block signal authentication")
        results = idx.search("block authentication")
        assert "ep-1" in results

    def test_no_match_returns_empty(self):
        idx = EmbeddingIndex()
        idx.index("ep-1", "unrelated content")
        results = idx.search("completely different query xyz")
        assert "ep-1" not in results

    def test_multiple_episodes_ranked(self):
        idx = EmbeddingIndex()
        idx.index("ep-1", "block signal critical authentication")
        idx.index("ep-2", "block signal")
        idx.index("ep-3", "inform signal low")
        results = idx.search("block signal critical authentication")
        assert results[0] == "ep-1"

    def test_remove_clears_episode(self):
        idx = EmbeddingIndex()
        idx.index("ep-1", "block signal")
        idx.remove("ep-1")
        results = idx.search("block signal")
        assert "ep-1" not in results


class TestPatternMiner:
    def test_mine_recurring_pattern(self):
        miner = PatternMiner()
        episodes = [
            {"source_product": "inspectra", "target_product": "anvil",
             "signal_type": "BLOCK", "outcome": "BLOCKED"},
        ] * 3
        patterns = miner.mine(episodes, min_occurrences=2)
        assert len(patterns) >= 1
        found = [p for p in patterns if p["pattern_type"] == "RECURRING_SIGNAL_OUTCOME"]
        assert len(found) >= 1
        assert found[0]["occurrence_count"] >= 3

    def test_mine_gravity_pattern(self):
        miner = PatternMiner()
        episodes = [
            {"source_product": "a", "target_product": "b",
             "signal_type": "BLOCK", "outcome": "ok", "gravity_action": "BLOCK"},
        ] * 4
        patterns = miner.mine(episodes, min_occurrences=2)
        gravity_patterns = [p for p in patterns if p["pattern_type"] == "GRAVITY_ACTION_PATTERN"]
        assert len(gravity_patterns) >= 1

    def test_no_pattern_below_threshold(self):
        miner = PatternMiner()
        episodes = [
            {"source_product": "a", "target_product": "b",
             "signal_type": "BLOCK", "outcome": "ok"},
        ]
        patterns = miner.mine(episodes, min_occurrences=3)
        recurring = [p for p in patterns if p["pattern_type"] == "RECURRING_SIGNAL_OUTCOME"]
        assert len(recurring) == 0


# ─── REST API tests ──────────────────────────────────────────────────────────

class TestMemoryAPI:
    def test_list_episodes_empty(self, client):
        resp = client.get("/memory/episodes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["episodes"] == []

    def test_get_episode_not_found(self, client):
        resp = client.get("/memory/episodes/nonexistent-id")
        assert resp.status_code == 404

    def test_recall_empty(self, client):
        resp = client.post("/memory/recall", json={"query": "block authentication"})
        assert resp.status_code == 200
        assert resp.json()["episodes"] == []

    def test_mine_patterns_empty(self, client):
        resp = client.post("/memory/mine-patterns")
        assert resp.status_code == 200
        assert resp.json()["patterns"] == []

    def test_snapshot_endpoint(self, client):
        resp = client.post("/memory/snapshot")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_list_episodes_with_product_filter(self, client):
        resp = client.get("/memory/episodes", params={"product": "anvil"})
        assert resp.status_code == 200

    def test_list_episodes_with_limit(self, client):
        resp = client.get("/memory/episodes", params={"limit": 10})
        assert resp.status_code == 200
