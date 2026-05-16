# API Reference

Base URL: `http://localhost:8000`

All requests/responses use JSON. Authentication is optional (see [Security](SECURITY.md)).

---

## Health

### `GET /health`
Returns server health.

```json
{"status": "ok", "version": "0.1.0", "uptime_seconds": 42.1}
```

---

## Products

### `POST /products/register`
Register a product with Corpus.

**Body:**
```json
{
  "name": "Anvil",
  "capabilities": ["task_management", "deploy"],
  "base_url": "http://anvil.internal"
}
```

**Response:** `201` — `{"product_id": "...", "name": "Anvil", ...}`

### `GET /products`
List all registered products.

### `DELETE /products/{product_id}`
Deregister a product.

---

## Signals

### `POST /signals`
Emit a signal.

**Body:**
```json
{
  "source_product": "CI",
  "target_product": "Anvil",
  "signal_type": "BLOCK",
  "severity": "HIGH",
  "message": "Build failed",
  "payload": {"run_id": "42"}
}
```

**Signal types:** `INFORM`, `WARN`, `BLOCK`, `ESCALATE`, `CONSULT`, `LEARN`, `VALIDATE`, `REROUTE`

**Severity:** `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`

### `GET /signals/pending?product_name=Anvil`
Get pending signals for a product.

### `POST /signals/{signal_id}/acknowledge`
Acknowledge (consume) a signal.

---

## Checkpoints

### `GET /checkpoints`
List checkpoints. Filter: `?status=WAITING_CLEARANCE`

### `GET /checkpoints/{checkpoint_id}`
Get a single checkpoint.

### `POST /checkpoints/{checkpoint_id}/approve`
Grant clearance.

### `POST /checkpoints/{checkpoint_id}/reject`
Reject a checkpoint.

---

## Orchestration

### `POST /orchestration/workflows`
Create an orchestration workflow.

**Body:**
```json
{
  "initiating_product": "Anvil",
  "action": "deploy auth-service v2.4.1",
  "required_capabilities": ["ci_status", "impact_analysis"],
  "context": {}
}
```

### `POST /orchestration/workflows/{id}/start`
Start workflow execution and get synthesized decision.

### `POST /orchestration/workflows/{id}/cancel`
Cancel a PENDING or RUNNING workflow.

### `GET /orchestration/workflows`
List workflows. Filter: `?status=COMPLETED&limit=20`

---

## Guardian

### `GET /guardian/status`
Guardian engine status (mode, thresholds, counts).

### `GET /guardian/interventions`
Recent interventions. Filter: `?limit=20`

---

## Dashboard

### `GET /dashboard/summary`
Full system summary aggregating all subsystems.

### `GET /dashboard/products`
Product presence and capability map.

### `GET /dashboard/checkpoints`
Checkpoint breakdown by status.

### `GET /dashboard/orchestrations`
Recent workflow list.

### `GET /dashboard/guardian`
Guardian status + interventions.

### `GET /dashboard/memory`
Recent episodes and patterns.

### `GET /dashboard/timeline`
Cross-system event timeline. Filter: `?limit=50`

---

## Policy

### `GET /policy`
Current governance policy (mode, trust levels, rules).

---

## Admin

### `GET /admin/config`
Runtime configuration (version, host, port, db path).

### `POST /admin/reload-policy`
Reload policy from default configuration.

---

## WebSocket

### `WS /ws/{product_name}`
Real-time signal stream. Receives `{"type": "signal", "signal": {...}}` messages.
