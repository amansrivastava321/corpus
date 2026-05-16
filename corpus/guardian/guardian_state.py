"""GuardianState — SQLite persistence for interventions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aiosqlite

from corpus.guardian.guardian_models import GuardianIntervention


class GuardianState:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save_intervention(self, intervention: GuardianIntervention) -> None:
        d = intervention.to_dict()
        await self._conn.execute(
            """INSERT INTO guardian_interventions
               (intervention_id, signal_id, action, reason, approved, dry_run, created_at, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(intervention_id) DO UPDATE SET
                 action=excluded.action, data=excluded.data""",
            (
                intervention.id,
                intervention.signal_id,
                intervention.action.value,
                intervention.reason,
                1 if intervention.approved_by_policy else 0,
                1 if intervention.dry_run else 0,
                intervention.created_at,
                json.dumps(d),
            ),
        )
        await self._conn.commit()

    async def get_intervention(self, intervention_id: str) -> GuardianIntervention | None:
        async with self._conn.execute(
            "SELECT data FROM guardian_interventions WHERE intervention_id = ?",
            (intervention_id,),
        ) as cur:
            row = await cur.fetchone()
        return GuardianIntervention.from_dict(json.loads(row[0])) if row else None

    async def list_interventions(
        self,
        limit: int = 50,
        action: str | None = None,
    ) -> list[GuardianIntervention]:
        q = "SELECT data FROM guardian_interventions WHERE 1=1"
        params: list = []
        if action:
            q += " AND action = ?"
            params.append(action)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        async with self._conn.execute(q, params) as cur:
            rows = await cur.fetchall()
        return [GuardianIntervention.from_dict(json.loads(r[0])) for r in rows]
