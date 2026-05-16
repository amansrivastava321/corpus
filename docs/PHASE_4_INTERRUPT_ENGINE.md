# Phase 4 — Checkpoint Interrupt Engine

Phase 4 transforms Corpus from a live coordination runtime into an **execution governance runtime**. Products can register execution checkpoints, request clearance before proceeding, and receive real-time governance decisions via WebSocket.

---

## Overview

A **checkpoint** is a first-class persistent entity that represents a point in a product's execution where it must receive clearance before proceeding. The checkpoint lifecycle flows through:

```
REGISTERED → WAITING_CLEARANCE → decision → RESOLVED | CANCELLED | EXPIRED
```

Clearance decisions are made by the **ClearanceEngine**, which evaluates active blocking signals against a priority-ordered rule set. If a BLOCK or ESCALATE signal is active for the product, execution is halted. Clearance decisions are pushed to the product over WebSocket in real time.

---

## Checkpoint Lifecycle

```
                    register()
                        │
                        ▼
                  REGISTERED
                        │
             request_clearance()
                        │
                        ▼
              WAITING_CLEARANCE
                        │
              ┌─────────┼─────────┬────────┬──────────┐
              ▼         ▼         ▼        ▼          ▼
           CLEARED   BLOCKED   DELAYED  REROUTED  ESCALATED
              │         │
          resolve()  cancel()
              │
              ▼
           RESOLVED
```

Terminal states: `RESOLVED`, `CANCELLED`, `EXPIRED`

---

## Decision Types

| Decision | Meaning | blocks continuation |
|---|---|---|
| `ALLOW` | No active threats — proceed | No |
| `WARN` | Low-severity concern — proceed with caution | No |
| `DELAY` | INTERRUPT signal active — pause and retry later | No |
| `BLOCK` | BLOCK signal active — halt execution | **Yes** |
| `REROUTE` | Alternative path required | No |
| `ESCALATE` | Requires human review | **Yes** |

---

## Clearance Engine

The `ClearanceEngine` is stateless — it evaluates a checkpoint synchronously and returns a decision:

1. Fetch all unacknowledged BLOCK / INTERRUPT / ESCALATE signals for the product
2. Apply priority-ordered `InterruptRules`
3. First matching rule wins → decision
4. No match → `ALLOW`

### Rule Priority (highest → lowest)

| Signal Type | Severity | Decision |
|---|---|---|
| BLOCK | CRITICAL | BLOCK |
| BLOCK | HIGH | BLOCK |
| ESCALATE | any | ESCALATE |
| INTERRUPT | CRITICAL | BLOCK |
| INTERRUPT | HIGH | DELAY |
| INTERRUPT | MEDIUM | DELAY |

---

## Interrupt Bridge (Reactive Path)

The `InterruptBridge` subscribes to `SIGNAL_EMITTED` events. When a BLOCK, INTERRUPT, or ESCALATE signal is emitted, it:

1. Checks whether any checkpoints for the target product are in `WAITING_CLEARANCE`
2. If yes, re-evaluates those checkpoints immediately
3. The new decision (if more severe) is persisted and pushed via WebSocket

This is the **reactive path**: signal arrives → governance runs automatically.

The **proactive path** is the product calling `request_clearance()` directly.

---

## Timeout Policies

Every checkpoint can be registered with a timeout:

```python
cp = client.checkpoints().register(
    "PRE_DEPLOY",
    product_id=my_id,
    timeout_seconds=300,
    timeout_policy="FAIL_OPEN",  # or FAIL_CLOSED, ESCALATE
)
```

| Policy | On Timeout |
|---|---|
| `FAIL_OPEN` | Decision: ALLOW — execution proceeds |
| `FAIL_CLOSED` | Decision: BLOCK — execution halted |
| `ESCALATE` | Decision: ESCALATE — human review required |

---

## REST API

### Register a checkpoint

```http
POST /checkpoints/register
{
  "product_id": "abc123",
  "checkpoint_type": "PRE_DEPLOY",
  "context": {"target": "production"},
  "timeout_seconds": 300,
  "timeout_policy": "FAIL_OPEN"
}
→ 201 { "id": "...", "status": "REGISTERED", ... }
```

### Request clearance

```http
POST /checkpoints/{id}/request-clearance
→ 200 { "decision_type": "ALLOW", "allows_continuation": true, ... }
```

### Resolve (execution succeeded)

```http
POST /checkpoints/{id}/resolve
→ 200 { "status": "RESOLVED", "resolved_at": "...", ... }
```

### Cancel

```http
POST /checkpoints/{id}/cancel
→ 200 { "status": "CANCELLED", ... }
```

### Query endpoints

```http
GET /checkpoints/{id}               → checkpoint state
GET /checkpoints?product_id=&status= → filtered list
GET /checkpoints/{id}/decision       → latest clearance decision
GET /checkpoints/{id}/history        → immutable audit trail
```

---

## WebSocket Interrupt Delivery

When a clearance decision is made for a connected product, Corpus pushes it over the live WebSocket connection:

```json
{
  "message_type": "CLEARANCE_DECISION",
  "checkpoint_id": "cp-abc123",
  "checkpoint_type": "PRE_DEPLOY",
  "decision_type": "ALLOW",
  "reason": "No blocking signals detected — execution cleared",
  "allows_continuation": true
}
```

For blocking decisions:

```json
{
  "message_type": "EXECUTION_BLOCKED",
  "checkpoint_id": "cp-abc123",
  "decision_type": "BLOCK",
  "reason": "Critical BLOCK signal active for this product",
  "trigger_signal_id": "sig-xyz",
  "allows_continuation": false
}
```

For escalations:

```json
{
  "message_type": "EXECUTION_ESCALATED",
  "checkpoint_id": "cp-abc123",
  "decision_type": "ESCALATE",
  "reason": "Checkpoint timed out — ESCALATE policy applied",
  "allows_continuation": false
}
```

---

## SDK Usage

### Basic checkpoint flow

```python
from corpus_sdk import CorpusClient

client = CorpusClient(product_name="Anvil")
client.connect()

cp_client = client.checkpoints()

# Register and await clearance
cp, decision = cp_client.register_and_clear(
    checkpoint_type="PRE_DEPLOY",
    product_id=client.product_id,
    context={"target": "production", "commit": "abc123"},
    timeout_seconds=120,
    timeout_policy="FAIL_OPEN",
)

if decision.allows_continuation:
    # Execute the deployment
    deploy()
    cp_client.resolve(cp.id)
else:
    print(f"Blocked: {decision.reason}")
    cp_client.cancel(cp.id)
```

### Manual step-by-step

```python
cp = cp_client.register("PRE_DEPLOY", product_id=client.product_id)
decision = cp_client.request_clearance(cp.id)

if decision.decision_type == "DELAY":
    # Wait and retry
    import time
    time.sleep(30)
    decision = cp_client.request_clearance(cp.id)

if decision.allows_continuation:
    run_critical_operation()
    cp_client.resolve(cp.id)
else:
    cp_client.cancel(cp.id)
```

### Query history

```python
history = cp_client.get_history(cp.id)
for event in history:
    print(f"{event['occurred_at']} — {event['event_type']}")
```

---

## Auditability

Every checkpoint state transition is recorded in the `checkpoint_events` table with:
- `event_id` — unique event UUID
- `event_type` — REGISTERED | CLEARANCE_REQUESTED | CLEARANCE_DECIDED | RESOLVED | CANCELLED | TIMEOUT
- `data` — JSON payload with decision details, signal IDs, policies
- `occurred_at` — ISO timestamp

Events are append-only and never modified. This forms an immutable governance trail.

---

## Architecture

```
CorpusContainer
├── CheckpointRepository          ← SQLite persistence
├── DecisionRepository            ← Decision storage
├── AuditLog                      ← Append-only event trail
├── ClearanceEngine               ← Stateless evaluator
│   └── InterruptRules            ← Priority-ordered rule set
├── InterruptBridge               ← Reactive path (signal→checkpoint)
│   └── subscribes: SIGNAL_EMITTED
└── CheckpointService             ← Application layer
    ├── register()
    ├── request_clearance()
    ├── resolve() / cancel()
    ├── enforce_timeouts()         ← Background monitor
    └── _push_ws_decision()        ← WS delivery
```

### Database schema

```sql
CREATE TABLE checkpoints (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    checkpoint_type TEXT NOT NULL,
    status TEXT NOT NULL,
    timeout_policy TEXT NOT NULL DEFAULT 'FAIL_OPEN',
    context TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT,
    timeout_at TEXT,
    decision_id TEXT
);

CREATE TABLE clearance_decisions (
    id TEXT PRIMARY KEY,
    checkpoint_id TEXT NOT NULL REFERENCES checkpoints(id),
    decision_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    decided_by TEXT NOT NULL DEFAULT 'clearance_engine',
    trigger_signal_id TEXT,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE checkpoint_events (
    event_id TEXT PRIMARY KEY,
    checkpoint_id TEXT NOT NULL REFERENCES checkpoints(id),
    event_type TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL
);
```
