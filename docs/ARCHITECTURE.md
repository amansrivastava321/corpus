# Corpus — Architecture Reference

## What is Corpus?

Corpus is an AI-native coordination and mediation layer that acts as the nervous system connecting autonomous software products. It routes structured signals, mediates execution interrupts, maintains episodic memory, and can translate intent between systems that speak different internal languages.

It is **not** a message queue, an MCP server, or a tool-calling wrapper. It is a coordination runtime.

---

## Core Concepts

### Signal
The fundamental unit of communication. Every interaction between products is expressed as a typed, severity-graded Signal. Signals carry a payload, metadata, and a routing intent.

```
Signal
├── id            UUID
├── type          INFORM | CONSULT | INTERRUPT | BLOCK | VALIDATE | LEARN | ESCALATE
├── severity      LOW | MEDIUM | HIGH | CRITICAL
├── source_product
├── target_product (null = broadcast)
├── payload       {}
├── metadata      { tags, context, requires_ack, broadcast }
├── status        PENDING → DELIVERED → ACKNOWLEDGED | EXPIRED | FAILED
├── correlation_id
├── parent_signal_id
└── ttl
```

### ProductRegistration
A product connects to Corpus by registering itself. Registration declares identity, capabilities, and delivery endpoints.

```
ProductRegistration
├── product_id    UUID
├── name
├── version
├── capabilities  [ EMIT_SIGNALS, RECEIVE_SIGNALS, INTERRUPT, BE_INTERRUPTED,
│                   AUDIT, VALIDATE, LEARN, ORCHESTRATE ]
├── endpoint      HTTP base URL
├── websocket_endpoint
├── heartbeat_interval
└── status        ACTIVE | INACTIVE | DEGRADED | UNKNOWN
```

### Checkpoint
A synchronisation point where a product pauses and requests clearance before executing a potentially risky operation. Products expose named checkpoints (`PRE_COMMIT`, `PRE_RELEASE`, etc.) and block until Corpus issues a `ClearanceDecision`.

### ClearanceDecision
Corpus's authoritative response to a Checkpoint. Immutable once issued.

```
ClearanceDecision.decision
├── ALLOW    — proceed
├── WARN     — proceed with logged caution
├── DELAY    — retry after delay_seconds
├── BLOCK    — do not proceed
├── ESCALATE — raise to human oversight
└── REROUTE  — redirect to reroute_target product
```

### Episode
Groups all signals, events, and decisions that form a coherent interaction narrative (e.g. "Inspectra triggered an interrupt on Anvil's PRE_COMMIT checkpoint after finding a critical auth bug").

---

## Architectural Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 10  Guardian Mode (predictive, pre-emptive)          │
├─────────────────────────────────────────────────────────────┤
│  Phase 9   Multi-Product Orchestration                       │
├─────────────────────────────────────────────────────────────┤
│  Phase 8   Policy & Governance Engine                        │
├─────────────────────────────────────────────────────────────┤
│  Phase 7   Episodic Memory & Learning                        │
├─────────────────────────────────────────────────────────────┤
│  Phase 6   AI Translation Engine (Ollama / local LLM)       │
├─────────────────────────────────────────────────────────────┤
│  Phase 5   Signal Gravity Engine                             │
├─────────────────────────────────────────────────────────────┤
│  Phase 4   Checkpoint Interrupt Engine                       │
├─────────────────────────────────────────────────────────────┤
│  Phase 3   Real-Time Signal Bus (WebSocket)                  │
├─────────────────────────────────────────────────────────────┤
│  Phase 2   Adapter SDK (corpus-sdk-python)                   │
├─────────────────────────────────────────────────────────────┤
│  Phase 1   Core Corpus Daemon (FastAPI + SQLite)             │
├─────────────────────────────────────────────────────────────┤
│  Phase 0 ★ Foundations & Contracts (schemas, validator)      │
└─────────────────────────────────────────────────────────────┘
```

---

## Design Principles

| Principle | Meaning |
|---|---|
| **Local-first** | Works fully offline; no cloud dependency |
| **Async-native** | Non-blocking from the ground up |
| **Graceful degradation** | Products operate independently if Corpus is unavailable |
| **Modular** | Each layer is independently replaceable |
| **Strongly typed** | Pydantic models + JSON Schema everywhere |
| **Reversible interrupts** | No checkpoint decision causes irreversible harm |
| **Adapter isolation** | Products connect via thin adapters; no tight coupling |

---

## Module Map

```
corpus/
├── schemas/        Pydantic models + SchemaValidator (Phase 0)
├── contracts/      JSON Schema files + generator (Phase 0)
├── api/            FastAPI router definitions (Phase 1)
├── registry/       Product registry (Phase 1)
├── storage/        Abstract repository + SQLite impl (Phase 1)
├── signal_engine/  Signal routing, delivery, TTL expiry (Phase 1)
├── websocket/      WebSocket server + presence tracking (Phase 3)
├── adapters/       Adapter base class (Phase 2)
├── coordination/   Checkpoint + clearance engine (Phase 4)
├── policy/         Governance rules + trust levels (Phase 8)
├── translation/    LLM-based intent translation (Phase 6)
├── memory/         Episodic memory + embedding index (Phase 7)
├── learning/       Pattern mining + feedback loops (Phase 7)
├── runtime/        Daemon lifecycle + CLI (Phase 1)
├── artifacts/      Persisted runtime state files
├── tests/          Pytest test suite
└── docs/           Architecture + reference docs
```

---

## Signal Gravity

Every signal has a **gravity weight** = `severity_weight × type_multiplier`.

| Severity | Weight |
|---|---|
| LOW | 1.0 |
| MEDIUM | 2.5 |
| HIGH | 5.0 |
| CRITICAL | 10.0 |

| Type | Multiplier |
|---|---|
| INFORM | 0.5 |
| LEARN | 0.7 |
| CONSULT | 1.0 |
| VALIDATE | 1.5 |
| INTERRUPT | 2.0 |
| ESCALATE | 2.5 |
| BLOCK | 3.0 |

A `CRITICAL BLOCK` has gravity `30.0` — the maximum. This triggers immediate interrupt routing.

---

## Checkpoint Lifecycle

```
Product raises Checkpoint (status: PENDING)
        ↓
Corpus evaluates signals + policy (status: EVALUATING)
        ↓
   ┌────┴────────────────────────────────────┐
ALLOW/WARN                           BLOCK/DELAY/ESCALATE/REROUTE
   │                                         │
Product proceeds              Product holds / reroutes / escalates
```

---

## Product Isolation Guarantee

Products **never** import Corpus internals. They interact only through:

1. The **HTTP REST API** (`/signals/emit`, `/signals/pending/{product}`, etc.)
2. The **WebSocket stream** for real-time push delivery
3. The **corpus-sdk-python** adapter (optional thin wrapper around the above)

Corpus can go offline and products continue to function — they simply operate without coordination until Corpus reconnects.
