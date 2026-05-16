"""MemoryClient — query episodic memory via the Corpus API."""

from __future__ import annotations

from typing import Any

from corpus_sdk.transport import BaseTransport


class MemoryClient:
    def __init__(self, transport: BaseTransport) -> None:
        self._transport = transport

    def list_episodes(
        self,
        product: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if product:
            params["product"] = product
        if status:
            params["status"] = status
        resp = self._transport.get("/memory/episodes", params=params)
        return resp.get("episodes", [])

    def get_episode(self, episode_id: str) -> dict[str, Any]:
        return self._transport.get(f"/memory/episodes/{episode_id}")

    def recall(
        self,
        query: str,
        source_product: str | None = None,
        target_product: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        resp = self._transport.post(
            "/memory/recall",
            {
                "query": query,
                "source_product": source_product,
                "target_product": target_product,
                "top_k": top_k,
            },
        )
        return resp.get("episodes", [])

    def mine_patterns(self) -> list[dict[str, Any]]:
        resp = self._transport.post("/memory/mine-patterns", {})
        return resp.get("patterns", [])

    def snapshot(self) -> dict[str, Any]:
        return self._transport.post("/memory/snapshot", {})
