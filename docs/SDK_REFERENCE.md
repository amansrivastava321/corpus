# SDK Reference

The `corpus_sdk` package (`sdk/python/`) provides a typed Python client for Corpus.

## Installation

```bash
pip install -e sdk/python
```

## CorpusClient

```python
from corpus_sdk import CorpusClient

client = CorpusClient(
    product_name="Anvil",        # required — used as the sender identity
    base_url="http://localhost:8000",  # default
)
client.connect()    # registers product with Corpus
# ... use client ...
client.disconnect()
```

### Signal methods

All methods accept `target: str`, `message: str`, and optional `payload: dict`.

| Method | Signal type | Severity |
|--------|-------------|----------|
| `client.inform(target, message)` | `INFORM` | `LOW` |
| `client.warn(target, message)` | `WARN` | `MEDIUM` |
| `client.block(target, message)` | `BLOCK` | `HIGH` |
| `client.escalate(target, message)` | `ESCALATE` | `CRITICAL` |
| `client.consult(target, message)` | `CONSULT` | `MEDIUM` |
| `client.learn(target, message, broadcast=False)` | `LEARN` | `LOW` |

### Receiving signals

```python
pending = client.get_pending()
for sig in pending["signals"]:
    print(sig["message"])
    client.acknowledge(sig["signal_id"])
```

### InProcessTransport

For testing, inject an HTTPX TestClient as transport:

```python
from corpus_sdk.transport import InProcessTransport
from fastapi.testclient import TestClient
from corpus.server import create_app

tc = TestClient(create_app(db_path=":memory:"))
transport = InProcessTransport(tc)
sdk = CorpusClient(product_name="Test", transport=transport)
sdk.connect()
```

## Integration adapters

Each integration adapter (`integrations/`) wraps `CorpusClient` for a specific product:

```python
from integrations.anvil.anvil_integration import AnvilCorpusIntegration

integration = AnvilCorpusIntegration(corpus_url="http://localhost:8000")
integration.connect()
integration.task_started("refactor auth", "auth.py")
integration.disconnect()
```

Available adapters:
- `integrations.anvil.anvil_integration.AnvilCorpusIntegration`
- `integrations.inspectra.inspectra_integration.InspectraCorpusIntegration`
- `integrations.graphify.graphify_integration.GraphifyCorpusIntegration`
- `integrations.github_actions.ci_integration.CICorpusIntegration`
- `integrations.webhook.webhook_integration.WebhookCorpusIntegration`
