"""Persistence layer for checkpoints, clearance decisions, and audit events.

All three repositories use the same SQLite connection as the rest of the
system — no separate DB, no ORM, no distributed anything.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import aiosqlite

from corpus.checkpoints.models import RuntimeCheckpoint, RuntimeDecision


class CheckpointRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, checkpoint: RuntimeCheckpoint) -> None:
        await self._conn.execute(
            """INSERT INTO checkpoints
               (checkpoint_id, product_id, product_name, checkpoint_type, status,
                timeout_policy, created_at, updated_at, resolved_at, timeout_at,
                decision_id, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                checkpoint.id,
                checkpoint.product_id,
                checkpoint.product_name,
                checkpoint.checkpoint_type,
                checkpoint.status.value,
                checkpoint.timeout_policy.value,
                checkpoint.created_at.isoformat(),
                checkpoint.updated_at.isoformat(),
                checkpoint.resolved_at.isoformat() if checkpoint.resolved_at else None,
                checkpoint.timeout_at.isoformat() if checkpoint.timeout_at else None,
                checkpoint.decision_id,
                checkpoint.model_dump_json(),
            ),
        )
        await self._conn.commit()

    async def update(self, checkpoint: RuntimeCheckpoint) -> None:
        await self._conn.execute(
            """UPDATE checkpoints
               SET status = ?, updated_at = ?, resolved_at = ?, decision_id = ?, data = ?
               WHERE checkpoint_id = ?""",
            (
                checkpoint.status.value,
                checkpoint.updated_at.isoformat(),
                checkpoint.resolved_at.isoformat() if checkpoint.resolved_at else None,
                checkpoint.decision_id,
                checkpoint.model_dump_json(),
                checkpoint.id,
            ),
        )
        await self._conn.commit()

    async def get(self, checkpoint_id: str) -> RuntimeCheckpoint | None:
        async with self._conn.execute(
            "SELECT data FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
        ) as cur:
            row = await cur.fetchone()
        return RuntimeCheckpoint.model_validate_json(row[0]) if row else None

    async def list_all(
        self,
        product_id: str | None = None,
        status: str | None = None,
    ) -> list[RuntimeCheckpoint]:
        query = "SELECT data FROM checkpoints WHERE 1=1"
        params: list[Any] = []
        if product_id:
            query += " AND product_id = ?"
            params.append(product_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        async with self._conn.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [RuntimeCheckpoint.model_validate_json(r[0]) for r in rows]

    async def list_waiting(self) -> list[RuntimeCheckpoint]:
        """All checkpoints currently awaiting clearance."""
        return await self.list_all(status="WAITING_CLEARANCE")

    async def list_expiring(self) -> list[RuntimeCheckpoint]:
        """All non-terminal checkpoints with a timeout_at in the past."""
        now = datetime.now(timezone.utc).isoformat()
        async with self._conn.execute(
            """SELECT data FROM checkpoints
               WHERE timeout_at IS NOT NULL
                 AND timeout_at <= ?
                 AND status NOT IN ('RESOLVED', 'CANCELLED', 'EXPIRED')""",
            (now,),
        ) as cur:
            rows = await cur.fetchall()
        return [RuntimeCheckpoint.model_validate_json(r[0]) for r in rows]


class DecisionRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, decision: RuntimeDecision) -> None:
        await self._conn.execute(
            """INSERT INTO clearance_decisions
               (decision_id, checkpoint_id, decision_type, reason, decided_by,
                trigger_signal_id, created_at, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                decision.id,
                decision.checkpoint_id,
                decision.decision_type.value,
                decision.reason,
                decision.decided_by,
                decision.trigger_signal_id,
                decision.created_at.isoformat(),
                decision.model_dump_json(),
            ),
        )
        await self._conn.commit()

    async def get(self, decision_id: str) -> RuntimeDecision | None:
        async with self._conn.execute(
            "SELECT data FROM clearance_decisions WHERE decision_id = ?", (decision_id,)
        ) as cur:
            row = await cur.fetchone()
        return RuntimeDecision.model_validate_json(row[0]) if row else None

    async def get_for_checkpoint(self, checkpoint_id: str) -> list[RuntimeDecision]:
        async with self._conn.execute(
            """SELECT data FROM clearance_decisions
               WHERE checkpoint_id = ?
               ORDER BY created_at ASC""",
            (checkpoint_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [RuntimeDecision.model_validate_json(r[0]) for r in rows]

    async def latest_for_checkpoint(self, checkpoint_id: str) -> RuntimeDecision | None:
        async with self._conn.execute(
            """SELECT data FROM clearance_decisions
               WHERE checkpoint_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (checkpoint_id,),
        ) as cur:
            row = await cur.fetchone()
        return RuntimeDecision.model_validate_json(row[0]) if row else None
