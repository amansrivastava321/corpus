# Quickstart

Get Corpus running in under 5 minutes.

## Prerequisites

- Python 3.11+
- pip

## Install

```bash
git clone https://github.com/your-org/corpus.git
cd corpus
pip install -e ".[dev]"
```

## Start the server

```bash
corpus serve --db :memory:
```

Or with uvicorn directly:

```bash
uvicorn corpus.server:app --reload
```

Visit `http://localhost:8000/health` to confirm the server is up.

## Register your first products

```bash
curl -X POST http://localhost:8000/products/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Anvil", "capabilities": ["task_management"]}'

curl -X POST http://localhost:8000/products/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Inspectra", "capabilities": ["security_scan"]}'
```

## Emit a signal

```bash
curl -X POST http://localhost:8000/signals \
  -H "Content-Type: application/json" \
  -d '{
    "source_product": "Anvil",
    "target_product": "Inspectra",
    "signal_type": "INFORM",
    "severity": "LOW",
    "message": "Refactor complete on auth.py"
  }'
```

## Use the Python SDK

```python
from corpus_sdk import CorpusClient

client = CorpusClient(product_name="Anvil", base_url="http://localhost:8000")
client.connect()

client.inform(target="Inspectra", message="Refactor complete on auth.py")
client.disconnect()
```

## Explore further

- [API Reference](API_REFERENCE.md)
- [SDK Reference](SDK_REFERENCE.md)
- [Architecture](ARCHITECTURE.md)
- [`examples/`](../examples/) — runnable demos
