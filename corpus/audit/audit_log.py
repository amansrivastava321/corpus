"""Append-only audit log for checkpoint lifecycle events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from corpus import log

_log = log.get_logger("corpus.audit")


class AuditLog:
    """Append-only audit trail for checkpoint lifecycle events.

    Every significant state transition for a checkpoint is recorded here:
    registration, clearance evaluation, blocking, resolution, timeout, etc.
    Records are never deleted or modified — they form an immutable timeline.
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def append(
        self,
        checkpoint_id: str,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Append an event to the audit trail."""
        import json
        now = datetime.now(timezone.utc).isoformat()
        event_id = str(uuid.uuid4())
        await self._conn.execute(
            """INSERT INTO checkpoint_events (event_id, checkpoint_id, event_type, data, occurred_at)
               VALUES (?, ?, ?, ?, ?)""",
            (event_id, checkpoint_id, event_type, json.dumps(data or {}), now),
        )
        await self._conn.commit()
        _log.debug(
            "audit.appended",
            checkpoint_id=checkpoint_id,
            event_type=event_type,
        )

    async def get_history(self, checkpoint_id: str) -> list[dict[str, Any]]:
        """Return the full event history for a checkpoint, oldest first."""
        import json
        async with self._conn.execute(
            """SELECT event_id, event_type, data, occurred_at
               FROM checkpoint_events
               WHERE checkpoint_id = ?
               ORDER BY occurred_at ASC""",
            (checkpoint_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [
            {
                "event_id": r[0],
                "event_type": r[1],
                "data": json.loads(r[2]),
                "occurred_at": r[3],
            }
            for r in rows
        ]
