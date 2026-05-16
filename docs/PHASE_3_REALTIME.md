# Corpus Phase 3 — Real-Time WebSocket Signal Bus

Phase 3 transforms Corpus from a request/response coordination system into a **live runtime coordination layer**.  Products no longer poll for signals — they connect, become present, and receive signals the instant they're emitted.

---

## Contents

1. [Architecture](#architecture)
2. [WebSocket Lifecycle](#websocket-lifecycle)
3. [Presence Model](#presence-model)
4. [Message Protocol](#message-protocol)
5. [Heartbeat Lifecycle](#heartbeat-lifecycle)
6. [Delivery Lifecycle](#delivery-lifecycle)
7. [SDK Realtime Usage](#sdk-realtime-usage)
8. [Reconnect Flow](#reconnect-flow)
9. [REST + Realtime Coexistence](#rest--realtime-coexistence)
10. [REST API Reference](#rest-api-reference)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Products                                 │
│                                                                 │
│   Anvil ──WS──┐          Inspectra ──REST──┐                   │
│               │                             │                   │
└───────────────┼─────────────────────────────┼───────────────────┘
                │  WebSocket                  │  HTTP
┌───────────────▼─────────────────────────────▼───────────────────┐
│                     Corpus Daemon                               │
│                                                                 │
│   WS /ws/products/{id}          REST /signals/emit              │
│          │                              │                       │
│   WebSocketService                SignalService                 │
│     ├── handle_connect()            emit()                      │
│     ├── handle_message()               │                        │
│     └── _on_signal_emitted() ◄─── EventBus (SIGNAL_EMITTED)    │
│                                        │                        │
│   ConnectionManager    PresenceTracker RealtimeDispatcher       │
│   product_id → WS      ONLINE/OFFLINE  push if connected        │
│                                        │                        │
│   HeartbeatMonitor                     │                        │
│   (background task)          SignalRepository (SQLite)          │
│                              DeliveryRepository                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key design decisions

**Event bus integration** — When a signal is emitted (REST or SDK), `SignalService` publishes a `SignalEmittedEvent`. `WebSocketService` subscribes to this event and dispatches the signal to any connected targets before the HTTP response is returned. Zero coupling between the signal emission path and the WebSocket layer.

**Graceful degradation** — If a product is offline, the signal stays `PENDING` in SQLite. When the product reconnects, all pending signals are flushed immediately over WebSocket. REST polling always works alongside realtime.

**Presence is independent** — `PresenceTracker` only reflects WebSocket connectivity. Products that only use the REST API remain absent from the presence registry.

---

## WebSocket Lifecycle

```
Product                              Corpus
   │                                    │
   │──── WS Upgrade ───────────────────►│  validate product registered
   │                                    │  accept()
   │◄─── CONNECTED {pending_count} ─────│  mark_online()
   │                                    │  publish ProductConnectedEvent
   │◄─── SIGNAL (×N, flushed) ──────────│  flush_pending()
   │                                    │
   │──── HEARTBEAT ─────────────────────►│  update last_seen
   │◄─── HEARTBEAT_ACK ─────────────────│
   │                                    │
   │◄─── SIGNAL (realtime) ─────────────│  on signal emit → dispatch
   │──── ACK {signal_id} ───────────────►│  acknowledge in DB
   │                                    │
   │◄─── PRESENCE_UPDATE (others) ──────│  when other products connect/disconnect
   │                                    │
   ×──── disconnect ────────────────────►│  mark_offline()
                                         │  publish ProductDisconnectedEvent
                                         │  broadcast PRESENCE_UPDATE (OFFLINE)
```

---

## Presence Model

Products can be in one of four states:

| Status | Meaning |
|---|---|
| `ONLINE` | Connected via WebSocket, heartbeat current |
| `STALE` | Connected or recently connected, but heartbeat overdue (`> stale_threshold` seconds) |
| `OFFLINE` | Not connected via WebSocket |
| `RECONNECTING` | Was connected, now disconnected, expected to reconnect |

### State transitions

```
connect()                         heartbeat missing
          ┌──────────────────┐   (> stale_threshold)
──────────► ONLINE            ├───────────────────────► STALE
          └──────────────────┘                              │
                 ▲                                          │ heartbeat missing
                 │ heartbeat received                       │ (> offline_threshold)
                 │                                          ▼
                 └──────────────────────────────────── OFFLINE ◄── disconnect()
```

**Default thresholds:**
- Stale threshold: 30 seconds without heartbeat
- Offline threshold: 60 seconds without heartbeat

Both are configurable per `HeartbeatMonitor` instance.

---

## Message Protocol

All messages are JSON. The `message_type` field discriminates the message type.

### Server → Client

**CONNECTED** — sent immediately after WebSocket upgrade is accepted
```json
{
  "message_type": "CONNECTED",
  "product_id": "uuid...",
  "product_name": "Anvil",
  "pending_count": 3
}
```

**SIGNAL** — a signal routed to this product (direct or broadcast)
```json
{
  "message_type": "SIGNAL",
  "signal": {
    "id": "uuid...",
    "type": "BLOCK",
    "severity": "CRITICAL",
    "source_product": "Inspectra",
    "target_product": "Anvil",
    "payload": {"reason": "Hardcoded secret detected"},
    "timestamp": "2026-05-16T10:00:00Z",
    ...
  }
}
```

**HEARTBEAT_ACK** — response to a client heartbeat
```json
{
  "message_type": "HEARTBEAT_ACK",
  "server_time": "2026-05-16T10:00:00Z"
}
```

**PRESENCE_UPDATE** — broadcast when any product's presence changes
```json
{
  "message_type": "PRESENCE_UPDATE",
  "product_id": "uuid...",
  "product_name": "Inspectra",
  "status": "ONLINE"
}
```

**ERROR** — sent when a client message cannot be processed
```json
{
  "message_type": "ERROR",
  "code": "ack_error",
  "detail": "No delivery record for signal ..."
}
```

### Client → Server

**HEARTBEAT** — sent periodically to maintain ONLINE status
```json
{"message_type": "HEARTBEAT"}
```

**ACK** — acknowledge a specific signal (removes from pending queue)
```json
{
  "message_type": "ACK",
  "signal_id": "uuid..."
}
```

---

## Heartbeat Lifecycle

The `HeartbeatMonitor` runs as a background asyncio task. Every `check_interval` seconds it scans all products and downgrades presence for those that missed their heartbeat.

```
Client side:                       Server side:
  every 20s: send HEARTBEAT  ──────► update last_seen
                                     respond HEARTBEAT_ACK

  [no heartbeat for 30s]
                              ──────► ONLINE → STALE

  [no heartbeat for 60s]
                              ──────► STALE → OFFLINE
                                      disconnect WebSocket
                                      publish ProductDisconnectedEvent
```

**In tests**: Call `container.heartbeat_monitor.check_stale()` directly to trigger stale detection without sleeping. Set `presence.last_seen` manually to simulate time passing.

---

## Delivery Lifecycle

Each signal gets one delivery record per target product in `signal_deliveries`. The status transitions:

```
PENDING ──► DELIVERED (pushed over WS)
    │               │
    │               └──► ACKNOWLEDGED (ACK received)
    │
    └──► ACKNOWLEDGED (REST /ack called directly)
    │
    └──► EXPIRED (signal TTL elapsed)
```

**Columns added in Phase 3:**
- `delivered_at` — timestamp when pushed over WebSocket
- `failed_at`    — timestamp when WS send failed (signal stays PENDING for polling)

Signals with status `DELIVERED` are no longer returned by `GET /signals/pending/{id}`, because they've been physically sent to the client. The client must ACK them to move to `ACKNOWLEDGED`.

---

## SDK Realtime Usage

```python
import asyncio
from corpus_sdk import CorpusClient

async def main():
    # 1. Register with Corpus (REST)
    client = CorpusClient(product_name="Anvil", base_url="http://localhost:8000")
    client.connect()

    # 2. Get a realtime client
    rt = client.connect_realtime()

    # 3. Subscribe to signals
    def handle_signal(signal: dict) -> None:
        print(f"Received {signal['type']} from {signal['source_product']}")
        if signal["type"] == "BLOCK":
            # halt execution
            ...

    rt.subscribe(callback=handle_signal)
    # Or filter by type:
    rt.subscribe(signal_types=["BLOCK", "INTERRUPT"], callback=handle_critical)

    # 4. Start listening (blocks, auto-reconnects)
    await rt.listen()

asyncio.run(main())
```

### Manual heartbeat

The realtime client sends heartbeats automatically every `heartbeat_interval` seconds (default: 20). You can send one manually:

```python
await rt.send_heartbeat()
```

### Acknowledge via WebSocket

```python
await rt.acknowledge(signal_id="uuid...")
```

### Graceful shutdown

```python
await rt.disconnect()
```

---

## Reconnect Flow

```
Product                              Corpus
   │                                    │
   ×── disconnect ─────────────────────►│  mark_offline()
   │                                    │  signals accumulate in PENDING queue
   │  [reconnect delay: 1s → 2s → 4s…] │
   │                                    │
   │──── WS Upgrade ───────────────────►│
   │◄─── CONNECTED {pending_count: N} ──│
   │◄─── SIGNAL ×N (flushed) ───────────│  flush_pending()
```

The `CorpusRealtimeClient` uses exponential back-off: 1s → 2s → 4s → 8s … up to `reconnect_max_delay` (default: 30s). Reset to 1s on successful reconnect.

Set `reconnect=False` to disable automatic reconnect:
```python
rt = client.connect_realtime(reconnect=False)
```

---

## REST + Realtime Coexistence

Phase 3 does **not** break any Phase 1 or Phase 2 REST behavior. Both coexist:

| Scenario | Behavior |
|---|---|
| Product offline, signal emitted | Signal stays `PENDING` in DB; available via `GET /signals/pending/{id}` |
| Product online via WS, signal emitted | Signal pushed immediately; status → `DELIVERED`; no longer in REST pending |
| Product online via WS, ACK via WS | Status → `ACKNOWLEDGED`; confirmed via REST pending (empty) |
| Product online via WS, ACK via REST | Same result — idempotent |
| Product reconnects | Pending + delivered-but-unacked signals flushed on connect |

REST polling always works as a fallback. WebSocket delivery is an optimisation on top.

---

## REST API Reference

### WebSocket

| Endpoint | Description |
|---|---|
| `WS /ws/products/{product_id}` | Open a live signal channel for a registered product |

`product_id` must be a registered product UUID.

### Presence

| Endpoint | Description |
|---|---|
| `GET /presence` | List presence for all products that have connected via WebSocket |
| `GET /presence/{product_id}` | Get presence for a specific product |

**GET /presence/{product_id} response:**
```json
{
  "product_id": "uuid...",
  "product_name": "Anvil",
  "status": "ONLINE",
  "connected": true,
  "connected_at": "2026-05-16T10:00:00Z",
  "last_seen": "2026-05-16T10:00:20Z",
  "disconnected_at": null
}
```
