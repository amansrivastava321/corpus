"""EpisodeStore — SQLite persistence for episodic memory."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aiosqlite


class EpisodeStore:
    """
    Stores and retrieves episodes from the `episodes` table.

    Each episode is a JSON blob capturing:
    - trigger signal, products involved
    - gravity/translation/policy/clearance results
    - outcome and learning notes
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, episode: dict) -> str:
        episode_id = episode.get("id") or str(uuid.uuid4())
        episode["id"] = episode_id
        now = datetime.now(timezone.utc).isoformat()
        episode.setdefault("created_at", now)
        episode["updated_at"] = now

        await self._conn.execute(
            """INSERT INTO episodes
               (episode_id, source_product, target_product, signal_type,
                status, created_at, updated_at, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(episode_id) DO UPDATE SET
                 status=excluded.status,
                 updated_at=excluded.updated_at,
                 data=excluded.data""",
            (
                episode_id,
                episode.get("source_product", ""),
                episode.get("target_product", ""),
                episode.get("signal_type", ""),
                episode.get("status", "OPEN"),
                episode.get("created_at", now),
                now,
                json.dumps(episode),
            ),
        )
        await self._conn.commit()
        return episode_id

    async def get(self, episode_id: str) -> dict | None:
        async with self._conn.execute(
            "SELECT data FROM episodes WHERE episode_id = ?", (episode_id,)
        ) as cur:
            row = await cur.fetchone()
        return json.loads(row[0]) if row else None

    async def list_for_product(
        self,
        product_name: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        if status:
            async with self._conn.execute(
                """SELECT data FROM episodes
                   WHERE (source_product = ? OR target_product = ?)
                     AND status = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (product_name, product_name, status, limit),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with self._conn.execute(
                """SELECT data FROM episodes
                   WHERE source_product = ? OR target_product = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (product_name, product_name, limit),
            ) as cur:
                rows = await cur.fetchall()
        return [json.loads(r[0]) for r in rows]

    async def list_all(self, limit: int = 100) -> list[dict]:
        async with self._conn.execute(
            "SELECT data FROM episodes ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
        return [json.loads(r[0]) for r in rows]

    async def search_by_signal_type(self, signal_type: str, limit: int = 50) -> list[dict]:
        async with self._conn.execute(
            """SELECT data FROM episodes WHERE signal_type = ?
               ORDER BY created_at DESC LIMIT ?""",
            (signal_type, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [json.loads(r[0]) for r in rows]

    async def save_pattern(self, pattern: dict) -> str:
        pattern_id = pattern.get("id") or str(uuid.uuid4())
        pattern["id"] = pattern_id
        now = datetime.now(timezone.utc).isoformat()
        pattern.setdefault("discovered_at", now)

        await self._conn.execute(
            """INSERT INTO patterns
               (pattern_id, pattern_type, occurrence_count, discovered_at, data)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(pattern_id) DO UPDATE SET
                 occurrence_count=excluded.occurrence_count,
                 data=excluded.data""",
            (
                pattern_id,
                pattern.get("pattern_type", "UNKNOWN"),
                pattern.get("occurrence_count", 1),
                pattern.get("discovered_at", now),
                json.dumps(pattern),
            ),
        )
        await self._conn.commit()
        return pattern_id

    async def list_patterns(self, min_occurrences: int = 2) -> list[dict]:
        async with self._conn.execute(
            """SELECT data FROM patterns WHERE occurrence_count >= ?
               ORDER BY occurrence_count DESC""",
            (min_occurrences,),
        ) as cur:
            rows = await cur.fetchall()
        return [json.loads(r[0]) for r in rows]
