# Corpus Phase 2 — SDK & Adapter System

The SDK turns Corpus from a daemon you call with HTTP into an ecosystem runtime you integrate natively. Products register, emit signals, and respond to each other through typed Python objects — no raw HTTP, no JSON wrangling.

---

## Contents

1. [Installation](#installation)
2. [Quickstart](#quickstart)
3. [Transport Layer](#transport-layer)
4. [CorpusClient Reference](#corpusclient-reference)
5. [Signal Types & Convenience Methods](#signal-types--convenience-methods)
6. [Pending Signals & Acknowledgement](#pending-signals--acknowledgement)
7. [Hooks](#hooks)
8. [Adapters](#adapters)
9. [Architecture](#architecture)
10. [Extension Guide](#extension-guide)

---

## Installation

The SDK lives in `sdk/python/` and is independently importable. In development, add both the project root and the SDK path to your Python path:

```bash
pip install -e .           # installs corpus (server)
pip install -e sdk/python  # installs corpus_sdk (client)
```

Or when running pytest, the `pyproject.toml` sets `pythonpath = [".", "sdk/python"]` automatically.

---

## Quickstart

```python
from corpus_sdk import CorpusClient

# Connect to a running Corpus daemon
client = CorpusClient(
    product_name="MyProduct",
    product_version="1.0.0",
    capabilities=["EMIT_SIGNALS", "RECEIVE_SIGNALS"],
    base_url="http://localhost:8000",
)

product = client.connect(description="Does useful things")
print(product.product_id)   # UUID assigned by Corpus

# Send a signal to another product
client.inform("OtherProduct", "Analysis started", {"module": "auth"})

# Poll for incoming signals
for signal in client.get_pending_signals():
    print(signal.signal_type, signal.source_product)
    client.acknowledge_signal(signal.id)

client.disconnect()
```

---

## Transport Layer

The transport abstraction decouples the client from HTTP. Two implementations are provided:

### `HTTPTransport` (production)

Uses `httpx` with configurable retries and timeouts. This is the default when you supply `base_url`.

```python
from corpus_sdk.transport import HTTPTransport
from corpus_sdk import CorpusClient

transport = HTTPTransport(
    base_url="http://localhost:8000",
    timeout=10.0,
    retries=3,
    retry_delay=0.5,
)
client = CorpusClient(product_name="Anvil", transport=transport)
```

Network errors surface as `CorpusConnectionError`. API errors map to typed exceptions (`SignalRoutingError`, `ProductAlreadyRegisteredError`, etc.).

### `InProcessTransport` (testing)

Wraps a Starlette `TestClient` so SDK tests run against a real in-memory Corpus server with zero network overhead:

```python
from fastapi.testclient import TestClient
from corpus.server import create_app
from corpus_sdk import CorpusClient, InProcessTransport

with TestClient(create_app(db_path=":memory:")) as tc:
    client = CorpusClient(
        product_name="Anvil",
        transport=InProcessTransport(tc),
    )
    client.connect()
    # ... test assertions
```

### Custom Transport

Subclass `BaseTransport` and implement `_request`:

```python
from corpus_sdk.transport import BaseTransport

class MyTransport(BaseTransport):
    def _request(self, method: str, path: str, **kwargs):
        # call your custom backend
        ...
```

---

## CorpusClient Reference

### Constructor

```python
CorpusClient(
    product_name: str,
    product_version: str = "0.1.0",
    capabilities: list[str] | None = None,
    base_url: str = "http://localhost:8000",
    timeout: float = 10.0,
    retries: int = 3,
    transport: BaseTransport | None = None,  # overrides base_url when provided
)
```

### Lifecycle

| Method | Description |
|---|---|
| `connect(description?, update_existing?, **metadata)` | Register with Corpus; returns `ProductInfo` |
| `disconnect()` | Unregister; clears local state |
| `heartbeat(status?)` | Update last-seen timestamp and optional status |

`update_existing=True` performs an upsert — updates version/metadata for an already-registered name while preserving its `product_id`.

### Properties

| Property | Type | Description |
|---|---|---|
| `product` | `ProductInfo \| None` | Full product info after connect |
| `product_id` | `str \| None` | UUID shorthand |
| `is_connected` | `bool` | True after successful connect |

### From config

```python
# reads CORPUS_BASE_URL, CORPUS_PRODUCT_NAME, etc. from environment
client = CorpusClient.from_config()
```

---

## Signal Types & Convenience Methods

Every signal has a **type** and **severity**. The client provides one convenience method per signal type so you never need to spell out `emit_signal` manually.

### Signal type reference

| Type | Default severity | Direction | Effect |
|---|---|---|---|
| `INFORM` | `LOW` | any → any | Informational; no action required |
| `CONSULT` | `MEDIUM` | any → any | Request advice before proceeding |
| `VALIDATE` | `MEDIUM` | any → any | Request formal validation of an artifact |
| `INTERRUPT` | `HIGH` | auditor → executor | Ask target to pause current operation |
| `BLOCK` | `CRITICAL` | auditor → executor | Halt target; must be acknowledged |
| `LEARN` | `LOW` | any → broadcast | Share a discovered pattern with all products |
| `ESCALATE` | `HIGH` | any → broadcast | Escalate unresolved situation to human oversight |

### Convenience methods

```python
# Directed signals
client.inform("Target", "message", payload_dict)
client.consult("Target", "question?", context_dict)
client.validate("Target", artifact_dict, scope=["security"])
client.interrupt("Target", "reason", severity="HIGH")
client.block("Target", "reason")

# Broadcasts (no target required)
client.learn("pattern_name", {"description": "...", "files": [...]})
client.escalate("reason", context={"unacked_ids": [...]})
```

### Low-level emit

```python
signal = client.emit_signal(
    signal_type="INFORM",       # or lowercase "inform"
    severity="LOW",             # or lowercase "low"
    target="OtherProduct",      # omit for broadcast
    payload={"key": "value"},
    intent="Optional question or intent string",
    ttl=300,                    # seconds until expiry
    requires_ack=True,
    broadcast=False,
    tags=["auth", "security"],
    correlation_id="episode-abc",
)
# returns EmittedSignal(id, signal_type, severity, broadcast, payload, ...)
```

---

## Pending Signals & Acknowledgement

Corpus queues signals for each registered product. Products poll for their queue and acknowledge each signal when handled.

```python
# Get all pending (unacknowledged) signals
signals = client.get_pending_signals()
# → list[ReceivedSignal]

# Acknowledge by ID
client.acknowledge_signal(signals[0].id)

# Batch: poll → handle → ack all
def my_handler(signal):
    print(f"Handling {signal.signal_type} from {signal.source_product}")

count = client.process_pending(handler=my_handler)
# count = number of signals processed and acknowledged
```

### `ReceivedSignal` fields

```python
signal.id               # UUID
signal.signal_type      # "BLOCK", "INFORM", etc.
signal.severity         # "CRITICAL", "HIGH", etc.
signal.source_product   # name of the sending product
signal.payload          # dict
signal.broadcast        # bool
signal.timestamp        # ISO string
```

---

## Hooks

Register callbacks that fire on client events without coupling signal logic to transport concerns.

```python
@client.hooks.on_signal_emitted
def on_emit(signal):
    metrics.increment("signals.emitted", tags=[signal.signal_type])

@client.hooks.on_signal_received
def on_receive(signal):
    logger.info("received", type=signal.signal_type, from_=signal.source_product)

@client.hooks.on_acknowledged
def on_ack(signal_id):
    logger.debug("acked", id=signal_id)

@client.hooks.on_error
def on_error(exc):
    sentry.capture_exception(exc)
```

Hooks fire synchronously in the calling thread. Errors in hooks are caught and do not propagate to the caller.

---

## Adapters

Adapters are opinionated wrappers around `CorpusClient` that expose domain-specific methods instead of raw signal primitives. The two reference adapters — **AnvilAdapter** and **InspectraAdapter** — demonstrate the pattern.

### AnvilAdapter

Anvil is an AI development orchestration platform. Its adapter exposes operations an execution engine needs:

```python
from corpus.adapters.anvil_adapter import AnvilAdapter
from corpus_sdk import InProcessTransport

anvil = AnvilAdapter.from_transport(transport)
# or: AnvilAdapter.from_url("http://localhost:8000")

anvil.connect(description="AI dev orchestration")

# Tell Inspectra that analysis is starting
anvil.notify_analysis_start("auth", ["auth/login.py", "auth/config.py"])

# Ask Inspectra to validate before committing
anvil.request_audit("auth", ["auth/login.py"], pr_id="42")

# Consult Inspectra before a risky change
anvil.consult_on_change("Is JWT migration safe?", {"current": "uuid4", "target": "JWT"})

# Broadcast execution start to all products
anvil.broadcast_execution_start("auth-refactor", {"pr": "42"})

# Poll for BLOCK/INTERRUPT signals
signals = anvil.receive()
for sig in signals:
    if sig.signal_type == "BLOCK":
        # halt execution
        pass

count = anvil.process_pending()   # poll + ack all; calls handle_signal() per signal
```

**Registered capabilities:** `EMIT_SIGNALS`, `RECEIVE_SIGNALS`, `BE_INTERRUPTED`, `VALIDATE`

### InspectraAdapter

Inspectra is an autonomous audit platform. Its adapter exposes security-domain operations:

```python
from corpus.adapters.inspectra_adapter import InspectraAdapter

inspectra = InspectraAdapter.from_transport(transport)
inspectra.connect(description="Autonomous audit")

# Block Anvil on a critical finding
inspectra.raise_critical_finding(
    "Anvil",
    "Hardcoded secret in auth/config.py:12",
    {"file": "auth/config.py", "line": 12},
)

# Request a pause (non-blocking severity)
inspectra.interrupt_execution("Anvil", "SQL injection risk detected", severity="HIGH")

# Broadcast a discovered pattern to all products
inspectra.share_pattern(
    "hardcoded_secret",
    "Secret keys defined as string literals instead of env vars",
)

# Report audit completion to the requesting product
inspectra.audit_complete("Anvil", passed=False, findings=[{"type": "sql_injection", "severity": "HIGH"}])

# Escalate an unresolved finding to human oversight
inspectra.escalate_unresolved("Block unacknowledged for 10 min", ["sig-001", "sig-002"])
```

**Registered capabilities:** `EMIT_SIGNALS`, `RECEIVE_SIGNALS`, `INTERRUPT`, `AUDIT`, `VALIDATE`, `LEARN`

### Building your own adapter

```python
from corpus.adapters.base import CorpusAdapter
from corpus_sdk.models import ReceivedSignal

class MyProductAdapter(CorpusAdapter):
    DEFAULT_NAME = "MyProduct"
    DEFAULT_VERSION = "1.0.0"
    DEFAULT_CAPABILITIES = ["EMIT_SIGNALS", "RECEIVE_SIGNALS"]

    @classmethod
    def from_transport(cls, transport):
        from corpus_sdk import CorpusClient
        client = CorpusClient(
            product_name=cls.DEFAULT_NAME,
            product_version=cls.DEFAULT_VERSION,
            capabilities=list(cls.DEFAULT_CAPABILITIES),
            transport=transport,
        )
        return cls(client=client)

    def do_my_thing(self, target: str) -> None:
        self.emit(
            signal_type="INFORM",
            severity="LOW",
            target=target,
            payload={"action": "my_thing_started"},
        )

    def handle_signal(self, signal: ReceivedSignal) -> None:
        if signal.signal_type == "BLOCK":
            self._on_block(signal)

    def _on_block(self, signal: ReceivedSignal) -> None:
        pass  # override to halt execution
```

The base `CorpusAdapter` provides:

| Method | Description |
|---|---|
| `connect(**kwargs)` | Delegates to `CorpusClient.connect()` |
| `disconnect()` | Delegates to `CorpusClient.disconnect()` |
| `heartbeat(status?)` | Delegates to `CorpusClient.heartbeat()` |
| `emit(signal_type, severity, **kwargs)` | Thin wrapper over `CorpusClient.emit_signal()` |
| `receive()` | Returns `list[ReceivedSignal]` without acknowledging |
| `acknowledge(signal_id)` | Acknowledges a single signal |
| `process_pending(handler?)` | Poll + call `handle_signal()` + ack all; returns count |
| `handle_signal(signal)` | Override in subclass to route by signal type |
| `is_connected` | Forwarded from client |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Your Product Code                      │
│                                                          │
│   AnvilAdapter / InspectraAdapter / CustomAdapter        │
│          │ domain methods (notify_analysis_start, ...)   │
│          ▼                                               │
│      CorpusAdapter (base)                                │
│          │ emit / receive / process_pending              │
│          ▼                                               │
│      CorpusClient                                        │
│          │ connect / emit_signal / get_pending / ack     │
│          ▼                                               │
│      BaseTransport                                       │
│     ┌────┴────┐                                          │
│     │         │                                          │
│ HTTPTransport  InProcessTransport                        │
│ (production)   (testing)                                 │
└────────────────┼─────────────────────────────────────────┘
                 │  HTTP / in-process
┌────────────────▼─────────────────────────────────────────┐
│                   Corpus Daemon                           │
│                                                          │
│   FastAPI routes                                         │
│       │ Depends(get_product_service / get_signal_service)│
│       ▼                                                  │
│   ProductService / SignalService                         │
│       │ orchestrates + publishes events                  │
│       ▼                                                  │
│   ProductRegistry / SignalRouter                         │
│       │ domain logic                                     │
│       ▼                                                  │
│   ProductRepository / SignalRepository (aiosqlite)       │
│                                                          │
│   EventBus ──► logging hooks, state hooks                │
└──────────────────────────────────────────────────────────┘
```

### Key design decisions

**Transport abstraction** — `CorpusClient` never touches `httpx` directly. The transport handles the wire protocol, error mapping, and retries. Swapping to a mock transport in tests gives the same code coverage as production without network overhead.

**SDK models are independent** — `corpus_sdk.models` (`ProductInfo`, `ReceivedSignal`, `EmittedSignal`) are plain dataclasses. They don't import from `corpus.schemas`. This means the SDK can be packaged and distributed separately from the server.

**Service layer as the single boundary** — Routes inject `ProductService` / `SignalService`, never the registry or router directly. This keeps business logic out of HTTP handlers and makes the services testable independently of FastAPI.

**EventBus for side effects** — Counter increments and structured logs are wired as event handlers, not scattered through business logic. Adding a new side effect (e.g. webhook delivery) means subscribing to an event, not touching the router.

---

## Extension Guide

### Adding a new signal type

1. Add the value to `SignalType` in `corpus/schemas/signal.py`
2. Add its gravity multiplier in `Signal.gravity_weight()`
3. Add a JSON Schema contract in `corpus/contracts/`
4. Add a convenience method to `CorpusClient` in `sdk/python/corpus_sdk/client.py`
5. Add a handler branch in the relevant adapter's `handle_signal()`

### Adding a new event

1. Add the event type to `CorpusEventType` in `corpus/events/event_types.py`
2. Define a `@dataclass` subclass of `CorpusEvent`
3. Publish via `await self._bus.publish(MyNewEvent(...))`
4. Subscribe in `corpus/events/hooks.py` or your own module

### Adding a new adapter

Subclass `CorpusAdapter` (see [Building your own adapter](#building-your-own-adapter) above). Place it in `corpus/adapters/`. Add integration tests in `tests/sdk/test_sdk_adapters.py` using `InProcessTransport`.

### Adding a new transport

Subclass `BaseTransport` from `corpus_sdk/transport.py` and implement `_request(method, path, **kwargs) -> Any`. Call `_raise_for(status_code, body)` to map HTTP errors to typed SDK exceptions.
