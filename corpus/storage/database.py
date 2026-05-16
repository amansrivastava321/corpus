"""SQLite database initialisation for the Corpus runtime.

All tables use TEXT columns for JSON payloads so the Pydantic models remain the
single source of truth for structure. The repository layer handles serialisation.
A Postgres swap requires only a new aiosqlite→asyncpg adapter in repositories.py.
"""

import aiosqlite

_CHECKPOINT_SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id  TEXT PRIMARY KEY,
    product_id     TEXT NOT NULL,
    product_name   TEXT NOT NULL,
    checkpoint_type TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'REGISTERED',
    timeout_policy TEXT NOT NULL DEFAULT 'FAIL_OPEN',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    resolved_at    TEXT,
    timeout_at     TEXT,
    decision_id    TEXT,
    data           TEXT NOT NULL   -- JSON: full RuntimeCheckpoint
);

CREATE TABLE IF NOT EXISTS clearance_decisions (
    decision_id       TEXT PRIMARY KEY,
    checkpoint_id     TEXT NOT NULL,
    decision_type     TEXT NOT NULL,
    reason            TEXT NOT NULL,
    decided_by        TEXT NOT NULL DEFAULT 'clearance_engine',
    trigger_signal_id TEXT,
    created_at        TEXT NOT NULL,
    data              TEXT NOT NULL   -- JSON: full RuntimeDecision
);

CREATE TABLE IF NOT EXISTS checkpoint_events (
    event_id      TEXT PRIMARY KEY,
    checkpoint_id TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    data          TEXT NOT NULL,  -- JSON
    occurred_at   TEXT NOT NULL
);
"""

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
    product_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    status       TEXT NOT NULL DEFAULT 'ACTIVE',
    registered_at TEXT NOT NULL,
    last_seen    TEXT,
    data         TEXT NOT NULL   -- JSON: full ProductRegistration
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id      TEXT PRIMARY KEY,
    type           TEXT NOT NULL,
    severity       TEXT NOT NULL,
    source_product TEXT NOT NULL,
    target_product TEXT,         -- NULL for broadcast
    is_broadcast   INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'PENDING',
    created_at     TEXT NOT NULL,
    expires_at     TEXT,         -- NULL = never expires
    data           TEXT NOT NULL  -- JSON: full Signal
);

CREATE TABLE IF NOT EXISTS signal_deliveries (
    signal_id    TEXT NOT NULL REFERENCES signals(signal_id),
    product_id   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | DELIVERED | ACKNOWLEDGED | FAILED | EXPIRED
    created_at   TEXT NOT NULL,
    delivered_at TEXT,   -- when pushed over WebSocket
    acked_at     TEXT,   -- when acknowledged (REST or WS ACK)
    failed_at    TEXT,   -- when WS delivery failed
    PRIMARY KEY (signal_id, product_id)
);
"""


_ORCHESTRATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS orchestration_workflows (
    workflow_id         TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    initiating_product  TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'PENDING',
    created_at          TEXT NOT NULL,
    started_at          TEXT,
    completed_at        TEXT,
    data                TEXT NOT NULL   -- JSON: full workflow dict
);

CREATE TABLE IF NOT EXISTS guardian_interventions (
    intervention_id TEXT PRIMARY KEY,
    signal_id       TEXT,
    action          TEXT NOT NULL,
    reason          TEXT NOT NULL,
    approved        INTEGER NOT NULL DEFAULT 1,
    dry_run         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    data            TEXT NOT NULL   -- JSON: full intervention dict
);
"""

_MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    episode_id     TEXT PRIMARY KEY,
    source_product TEXT NOT NULL,
    target_product TEXT NOT NULL,
    signal_type    TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'OPEN',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    data           TEXT NOT NULL   -- JSON: full episode dict
);

CREATE TABLE IF NOT EXISTS patterns (
    pattern_id       TEXT PRIMARY KEY,
    pattern_type     TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    discovered_at    TEXT NOT NULL,
    data             TEXT NOT NULL   -- JSON: full pattern dict
);
"""


async def init_db(conn: aiosqlite.Connection) -> None:
    """Create all tables if they do not already exist."""
    await conn.executescript(_SCHEMA)
    await conn.executescript(_CHECKPOINT_SCHEMA)
    await conn.executescript(_MEMORY_SCHEMA)
    await conn.executescript(_ORCHESTRATION_SCHEMA)
    await conn.commit()
