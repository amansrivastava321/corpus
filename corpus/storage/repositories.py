"""
Data-access repositories for the Corpus runtime.

Each class wraps raw aiosqlite SQL. No business logic lives here — that belongs
in ProductRegistry and SignalRouter. Swapping to Postgres means replacing these
classes with asyncpg equivalents behind the same interface.
"""

from datetime import datetime, timezone

import aiosqlite

from corpus.schemas import ProductRegistration, Signal


class ProductRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, product: ProductRegistration) -> None:
        await self._conn.execute(
            """INSERT INTO products (product_id, name, status, registered_at, last_seen, data)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                product.product_id,
                product.name,
                product.status.value,
                product.registered_at.isoformat(),
                product.last_seen.isoformat() if product.last_seen else None,
                product.model_dump_json(),
            ),
        )
        await self._conn.commit()

    async def update(self, product: ProductRegistration) -> None:
        await self._conn.execute(
            """UPDATE products
               SET name = ?, status = ?, last_seen = ?, data = ?
               WHERE product_id = ?""",
            (
                product.name,
                product.status.value,
                product.last_seen.isoformat() if product.last_seen else None,
                product.model_dump_json(),
                product.product_id,
            ),
        )
        await self._conn.commit()

    async def get_by_id(self, product_id: str) -> ProductRegistration | None:
        async with self._conn.execute(
            "SELECT data FROM products WHERE product_id = ?", (product_id,)
        ) as cur:
            row = await cur.fetchone()
        return ProductRegistration.model_validate_json(row[0]) if row else None

    async def get_by_name(self, name: str) -> ProductRegistration | None:
        async with self._conn.execute(
            "SELECT data FROM products WHERE LOWER(name) = LOWER(?)", (name,)
        ) as cur:
            row = await cur.fetchone()
        return ProductRegistration.model_validate_json(row[0]) if row else None

    async def list_all(self) -> list[ProductRegistration]:
        async with self._conn.execute("SELECT data FROM products ORDER BY registered_at") as cur:
            rows = await cur.fetchall()
        return [ProductRegistration.model_validate_json(r[0]) for r in rows]

    async def delete(self, product_id: str) -> bool:
        async with self._conn.execute(
            "DELETE FROM products WHERE product_id = ?", (product_id,)
        ) as cur:
            changed = cur.rowcount > 0
        await self._conn.commit()
        return changed


class SignalRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, signal: Signal, expires_at: str | None) -> None:
        await self._conn.execute(
            """INSERT INTO signals
               (signal_id, type, severity, source_product, target_product,
                is_broadcast, status, created_at, expires_at, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal.id,
                signal.type.value,
                signal.severity.value,
                signal.source_product,
                signal.target_product,
                1 if signal.metadata.broadcast else 0,
                signal.status.value,
                signal.timestamp.isoformat(),
                expires_at,
                signal.model_dump_json(),
            ),
        )
        await self._conn.commit()

    async def get(self, signal_id: str) -> Signal | None:
        async with self._conn.execute(
            "SELECT data FROM signals WHERE signal_id = ?", (signal_id,)
        ) as cur:
            row = await cur.fetchone()
        return Signal.model_validate_json(row[0]) if row else None

    async def get_pending_for_product(self, product_id: str) -> list[Signal]:
        """Return non-expired signals that have a PENDING delivery for *product_id*."""
        now = datetime.now(timezone.utc).isoformat()
        async with self._conn.execute(
            """SELECT s.data
               FROM signals s
               JOIN signal_deliveries sd ON s.signal_id = sd.signal_id
               WHERE sd.product_id = ?
                 AND sd.status = 'PENDING'
                 AND (s.expires_at IS NULL OR s.expires_at > ?)
               ORDER BY s.created_at ASC""",
            (product_id, now),
        ) as cur:
            rows = await cur.fetchall()
        return [Signal.model_validate_json(r[0]) for r in rows]

    async def count_pending(self) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) FROM signal_deliveries WHERE status = 'PENDING'"
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else 0

    async def get_blocking_signals_for_product(self, product_id: str) -> list[Signal]:
        """Return unacknowledged BLOCK/INTERRUPT/ESCALATE signals targeting this product.

        Used by the clearance engine to determine if execution should be blocked.
        Results are ordered: CRITICAL first, then by type severity (BLOCK > INTERRUPT > ESCALATE).
        """
        now = datetime.now(timezone.utc).isoformat()
        async with self._conn.execute(
            """SELECT s.data
               FROM signals s
               JOIN signal_deliveries sd ON s.signal_id = sd.signal_id
               WHERE sd.product_id = ?
                 AND sd.status IN ('PENDING', 'DELIVERED')
                 AND (s.expires_at IS NULL OR s.expires_at > ?)
                 AND s.type IN ('BLOCK', 'INTERRUPT', 'ESCALATE')
               ORDER BY
                 CASE s.severity
                   WHEN 'CRITICAL' THEN 0
                   WHEN 'HIGH'     THEN 1
                   WHEN 'MEDIUM'   THEN 2
                   WHEN 'LOW'      THEN 3
                 END ASC,
                 CASE s.type
                   WHEN 'BLOCK'     THEN 0
                   WHEN 'INTERRUPT' THEN 1
                   WHEN 'ESCALATE'  THEN 2
                 END ASC""",
            (product_id, now),
        ) as cur:
            rows = await cur.fetchall()
        return [Signal.model_validate_json(r[0]) for r in rows]


class DeliveryRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(self, signal_id: str, product_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """INSERT OR IGNORE INTO signal_deliveries (signal_id, product_id, status, created_at)
               VALUES (?, ?, 'PENDING', ?)""",
            (signal_id, product_id, now),
        )
        # commit is deferred to caller so batch inserts can share one commit

    async def acknowledge(self, signal_id: str, product_id: str) -> bool:
        """Mark a delivery as ACKNOWLEDGED. Returns False if no matching PENDING record."""
        now = datetime.now(timezone.utc).isoformat()
        async with self._conn.execute(
            """UPDATE signal_deliveries
               SET status = 'ACKNOWLEDGED', acked_at = ?
               WHERE signal_id = ? AND product_id = ? AND status = 'PENDING'""",
            (now, signal_id, product_id),
        ) as cur:
            updated = cur.rowcount > 0
        await self._conn.commit()
        return updated

    async def exists(self, signal_id: str, product_id: str) -> bool:
        async with self._conn.execute(
            "SELECT 1 FROM signal_deliveries WHERE signal_id = ? AND product_id = ?",
            (signal_id, product_id),
        ) as cur:
            return await cur.fetchone() is not None

    async def get_status(self, signal_id: str, product_id: str) -> str | None:
        async with self._conn.execute(
            "SELECT status FROM signal_deliveries WHERE signal_id = ? AND product_id = ?",
            (signal_id, product_id),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def mark_delivered(self, signal_id: str, product_id: str) -> None:
        """Record that this delivery was pushed over WebSocket."""
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """UPDATE signal_deliveries
               SET status = 'DELIVERED', delivered_at = ?
               WHERE signal_id = ? AND product_id = ? AND status = 'PENDING'""",
            (now, signal_id, product_id),
        )
        await self._conn.commit()

    async def mark_failed(self, signal_id: str, product_id: str) -> None:
        """Record that WebSocket delivery failed — signal remains in PENDING for polling."""
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """UPDATE signal_deliveries
               SET failed_at = ?
               WHERE signal_id = ? AND product_id = ?""",
            (now, signal_id, product_id),
        )
        await self._conn.commit()

    async def get_delivery_targets(self, signal_id: str) -> list[str]:
        """Return product_ids with a PENDING or DELIVERED record for this signal."""
        async with self._conn.execute(
            """SELECT product_id FROM signal_deliveries
               WHERE signal_id = ? AND status IN ('PENDING', 'DELIVERED')""",
            (signal_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [r[0] for r in rows]
