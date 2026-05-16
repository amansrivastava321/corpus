"""OrchestrationState — SQLite persistence for workflows."""

from __future__ import annotations

import json

import aiosqlite

from corpus.orchestration.orchestration_models import OrchestrationWorkflow


class OrchestrationState:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, workflow: OrchestrationWorkflow) -> None:
        d = workflow.to_dict()
        await self._conn.execute(
            """INSERT INTO orchestration_workflows
               (workflow_id, name, initiating_product, status, created_at,
                started_at, completed_at, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(workflow_id) DO UPDATE SET
                 status=excluded.status,
                 started_at=excluded.started_at,
                 completed_at=excluded.completed_at,
                 data=excluded.data""",
            (
                workflow.id,
                workflow.name,
                workflow.initiating_product,
                workflow.status.value,
                workflow.created_at,
                workflow.started_at,
                workflow.completed_at,
                json.dumps(d),
            ),
        )
        await self._conn.commit()

    async def get(self, workflow_id: str) -> OrchestrationWorkflow | None:
        async with self._conn.execute(
            "SELECT data FROM orchestration_workflows WHERE workflow_id = ?",
            (workflow_id,),
        ) as cur:
            row = await cur.fetchone()
        return OrchestrationWorkflow.from_dict(json.loads(row[0])) if row else None

    async def list_all(
        self,
        initiating_product: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[OrchestrationWorkflow]:
        q = "SELECT data FROM orchestration_workflows WHERE 1=1"
        params: list = []
        if initiating_product:
            q += " AND initiating_product = ?"
            params.append(initiating_product)
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        async with self._conn.execute(q, params) as cur:
            rows = await cur.fetchall()
        return [OrchestrationWorkflow.from_dict(json.loads(r[0])) for r in rows]
