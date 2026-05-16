# Corpus Phase 1 — Core Daemon

## Overview

Phase 1 delivers the first running Corpus server: a FastAPI-based local daemon that
registers products, receives signals, persists them in SQLite, routes them to target
products, and exposes a polling queue for pending delivery.

---

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Start the daemon (default: http://0.0.0.0:8000)
python -m corpus

# Or via uvicorn directly (auto-reload for dev)
uvicorn corpus.server:app --reload
```

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `CORPUS_DB_PATH` | `corpus.db` | SQLite database path |
| `CORPUS_HOST` | `0.0.0.0` | Bind address |
| `CORPUS_PORT` | `8000` | Port |

---

## API Reference

### System

#### `GET /health`

Returns runtime health and counters.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "version": "0.1.0",
  "products_registered": 2,
  "pending_deliveries": 1,
  "started_at": "2024-05-01T08:00:00+00:00",
  "uptime_seconds": 42.3,
  "total_signals_received": 5,
  "total_products_registered": 2,
  "expired_signals_skipped": 0,
  "last_error": null
}
```

---

### Products

#### `POST /products/register`

Register a product with Corpus.

```bash
curl -X POST http://localhost:8000/products/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Anvil",
    "version": "0.9.0",
    "capabilities": ["EMIT_SIGNALS", "RECEIVE_SIGNALS", "BE_INTERRUPTED"],
    "endpoint": "http://localhost:8100",
    "websocket_endpoint": "ws://localhost:8100/ws/corpus"
  }'
```

- Returns `201` with the full `ProductRegistration` on success.
- Returns `409 Conflict` if a product with that name is already registered.
- Add `?update_existing=true` to upsert instead of reject.

#### `POST /products/{product_id}/heartbeat`

Signal that a product is alive and update its status.

```bash
curl -X POST http://localhost:8000/products/aaaaaaaa-0000-0000-0000-000000000001/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"product_id": "aaaaaaaa-...", "status": "ACTIVE"}'
```

#### `GET /products`

List all registered products.

```bash
curl http://localhost:8000/products
```

#### `GET /products/{product_id}`

Retrieve a product by UUID or name (case-insensitive).

```bash
curl http://localhost:8000/products/Anvil
curl http://localhost:8000/products/aaaaaaaa-0000-0000-0000-000000000001
```

#### `DELETE /products/{product_id}`

Unregister a product.

```bash
curl -X DELETE http://localhost:8000/products/Anvil
```

---

### Signals

#### `POST /signals/emit`

Emit a signal from one product to another (or broadcast to all).

**Direct signal (Inspectra → Anvil):**
```bash
curl -X POST http://localhost:8000/signals/emit \
  -H "Content-Type: application/json" \
  -d '{
    "type": "BLOCK",
    "severity": "CRITICAL",
    "source_product": "Inspectra",
    "target_product": "Anvil",
    "payload": {
      "reason": "Hardcoded secret found in auth/config.py:12",
      "required_action": "Rotate and move to env var"
    },
    "metadata": {"requires_ack": true, "tags": ["auth", "critical"]}
  }'
```

**Broadcast signal (to all registered products):**
```bash
curl -X POST http://localhost:8000/signals/emit \
  -H "Content-Type: application/json" \
  -d '{
    "type": "LEARN",
    "severity": "LOW",
    "source_product": "Inspectra",
    "metadata": {"broadcast": true},
    "payload": {"pattern": "hardcoded_secret_in_config"}
  }'
```

- Returns `202 Accepted` with the full `Signal` on success.
- Returns `422` if target is not a registered product.
- Returns `410 Gone` if the signal was already expired at emit time.

#### `GET /signals/pending/{product_id}`

Poll for signals waiting to be delivered to a product.

```bash
curl http://localhost:8000/signals/pending/Anvil
```

Returns an array of `Signal` objects ordered by creation time. Only non-expired,
unacknowledged signals are returned.

`product_id` may be a UUID or the product's name.

#### `POST /signals/{signal_id}/ack`

Acknowledge receipt and processing of a signal.

```bash
curl -X POST http://localhost:8000/signals/11111111-0000-0000-0000-000000000001/ack \
  -H "Content-Type: application/json" \
  -d '{"product_id": "Anvil"}'
```

- Returns `200` with `{"status": "acknowledged", "signal_id": "...", "product_id": "..."}`.
- Returns `404` if the signal does not exist.
- Returns `422` if this product has no delivery record for this signal.
- Idempotent: acking an already-acknowledged signal returns `200`.

#### `GET /signals/{signal_id}`

Retrieve a signal by ID.

```bash
curl http://localhost:8000/signals/11111111-0000-0000-0000-000000000001
```

---

## Complete Scenario Walkthrough

```bash
BASE=http://localhost:8000

# 1. Start the daemon
python -m corpus

# 2. Register Anvil
curl -s -X POST $BASE/products/register \
  -H 'Content-Type: application/json' \
  -d '{"name":"Anvil","version":"0.9.0","capabilities":["RECEIVE_SIGNALS","BE_INTERRUPTED"]}' \
  | jq .product_id

# 3. Register Inspectra
curl -s -X POST $BASE/products/register \
  -H 'Content-Type: application/json' \
  -d '{"name":"Inspectra","version":"1.2.0","capabilities":["EMIT_SIGNALS","AUDIT","INTERRUPT"]}' \
  | jq .product_id

# 4. Inspectra emits a BLOCK signal to Anvil
SIG=$(curl -s -X POST $BASE/signals/emit \
  -H 'Content-Type: application/json' \
  -d '{
    "type":"BLOCK",
    "severity":"CRITICAL",
    "source_product":"Inspectra",
    "target_product":"Anvil",
    "payload":{"reason":"Hardcoded secret in auth/config.py:12"}
  }')
SIGNAL_ID=$(echo $SIG | jq -r .id)

# 5. Anvil polls its pending signals
curl -s $BASE/signals/pending/Anvil | jq .

# 6. Anvil acknowledges the signal
curl -s -X POST $BASE/signals/$SIGNAL_ID/ack \
  -H 'Content-Type: application/json' \
  -d '{"product_id":"Anvil"}'

# 7. Confirm the queue is now empty
curl -s $BASE/signals/pending/Anvil | jq length   # → 0

# 8. Check health
curl -s $BASE/health | jq .
```

---

## Product Lifecycle

```
                 POST /products/register
                         ↓
                   [ACTIVE status]
                         ↓
         POST /products/{id}/heartbeat  (periodic)
                         ↓
                  last_seen updated
                         ↓
           No heartbeat for 3× interval
                         ↓
                  is_stale() = True
                  (Phase 3 will evict)
                         ↓
         DELETE /products/{id}  (manual or auto)
```

---

## Signal Lifecycle

```
POST /signals/emit
        ↓
  Signal validated (TTL, target)
        ↓
  Signal persisted (signals table)
        ↓
  Delivery record created (signal_deliveries table)
  ├── Direct:    one record for target product
  └── Broadcast: one record per registered product (excl. source)
        ↓
GET /signals/pending/{product_id}   ← product polls
        ↓
  Non-expired PENDING deliveries returned
        ↓
POST /signals/{id}/ack
        ↓
  Delivery marked ACKNOWLEDGED
  Signal no longer appears in pending queue
```

---

## Storage Model

**SQLite tables:**

```
products
├── product_id   TEXT PK
├── name         TEXT UNIQUE
├── status       TEXT
├── registered_at TEXT
├── last_seen    TEXT
└── data         TEXT  (JSON: full ProductRegistration)

signals
├── signal_id    TEXT PK
├── type         TEXT
├── severity     TEXT
├── source_product TEXT
├── target_product TEXT
├── is_broadcast INTEGER
├── status       TEXT
├── created_at   TEXT
├── expires_at   TEXT
└── data         TEXT  (JSON: full Signal)

signal_deliveries
├── signal_id  TEXT → signals(signal_id)
├── product_id TEXT
├── status     TEXT  (PENDING | ACKNOWLEDGED)
├── created_at TEXT
└── acked_at   TEXT
```

JSON blobs store the full Pydantic model so the repository layer can reconstruct
typed objects without column proliferation. Indexed columns (type, severity, etc.)
are duplicated at the column level for efficient queries.

---

## Module Map

```
corpus/
├── config.py                  Settings (DB_PATH, HOST, PORT)
├── errors.py                  Typed error hierarchy
├── dependencies.py            FastAPI dependency functions
├── server.py                  App factory + lifespan + exception handlers
├── __main__.py                python -m corpus entry point
├── api/
│   ├── products.py            /products routes
│   └── signals.py             /signals routes
├── storage/
│   ├── database.py            SQL schema + init_db()
│   └── repositories.py        ProductRepository, SignalRepository, DeliveryRepository
├── registry/
│   └── product_registry.py    ProductRegistry (business logic)
├── signal_engine/
│   └── router.py              SignalRouter (routing + delivery logic)
└── runtime/
    └── state.py               RuntimeState (in-memory counters)
```

---

## Running Tests

```bash
# All tests (Phase 0 + Phase 1)
pytest tests/ -v

# Phase 1 only
pytest tests/test_products.py tests/test_signals.py tests/test_health.py -v
```

Each test uses an isolated `:memory:` SQLite database — no cleanup required.
