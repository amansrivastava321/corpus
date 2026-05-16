# Corpus

**AI-native coordination and mediation layer between autonomous software systems.**

Corpus is the nervous system connecting intelligent products. It routes structured signals, mediates execution interrupts, maintains episodic memory, translates intent between systems, orchestrates multi-product workflows, and enforces governance policy — all locally, without cloud dependencies.

---

## What Corpus Is Not

- Not a simple MCP server
- Not a tool-calling wrapper
- Not a message queue
- Not a basic event bus

## What Corpus Is

A coordination runtime that allows autonomous products to:

- communicate in real-time via typed, severity-graded signals
- interrupt one another safely and reversibly
- coordinate complex multi-product deploy decisions
- share learned patterns and episodic memory
- translate intent across different internal representations
- operate under policy-governed Guardian mode

---

## Quick Start

```bash
# Install (Python 3.11+)
pip install -e ".[dev]"
pip install -e sdk/python

# Start the server
corpus serve --db :memory:

# Check health
corpus doctor
```

Or with uvicorn:

```bash
uvicorn corpus.server:app --reload
```

---

## CLI

```bash
corpus serve                          # start the server
corpus doctor                         # health check
corpus products list                  # registered products
corpus signals emit \
  --source Anvil --target Inspectra \
  --type BLOCK --severity HIGH \
  --message "Auth refactor in progress"
corpus signals pending --target Anvil # pending signals
corpus checkpoints list               # all checkpoints
corpus policy show                    # current governance policy
corpus guardian status                # guardian engine status
corpus dashboard summary              # full system overview
corpus export -o state.json           # export state
corpus import state.json              # import products
```

All commands accept `--url http://your-corpus-server:8000` or set `CORPUS_URL`.

---

## Python SDK

```python
from corpus_sdk import CorpusClient

client = CorpusClient(product_name="Anvil", base_url="http://localhost:8000")
client.connect()

# Emit signals
client.inform("Inspectra", "Starting auth module refactor")
client.block("Inspectra", "Critical bug found", payload={"file": "auth.py"})

# Poll pending signals
for sig in client.get_pending()["signals"]:
    print(sig["message"])
    client.acknowledge(sig["signal_id"])

client.disconnect()
```

---

## Integration Adapters

```python
from integrations.anvil.anvil_integration import AnvilCorpusIntegration
from integrations.github_actions.ci_integration import CICorpusIntegration
from integrations.webhook.webhook_integration import WebhookCorpusIntegration

# Anvil
anvil = AnvilCorpusIntegration(corpus_url="http://localhost:8000")
anvil.connect()
anvil.task_started("refactor auth", "auth.py")

# CI
ci = CICorpusIntegration(corpus_url="http://localhost:8000")
ci.connect()
ci.report_ci_failure("my-org/repo", "main", "https://github.com/.../42")

# GitHub Webhooks
webhook = WebhookCorpusIntegration(corpus_url="http://localhost:8000")
webhook.connect()
webhook.handle_event("deployment_status.failure", payload)
```

---

## Multi-Product Orchestration

```python
import httpx

with httpx.Client(base_url="http://localhost:8000") as c:
    resp = c.post("/orchestration/workflows", json={
        "initiating_product": "Anvil",
        "action": "deploy auth-service v2.4.1",
        "required_capabilities": ["ci_status", "impact_analysis"],
    })
    wf_id = resp.json()["id"]

    result = c.post(f"/orchestration/workflows/{wf_id}/start").json()
    print(result["synthesized_decision"]["decision"])  # ALLOW or BLOCK
```

---

## Signal Model

| Type | Intent | Severity |
|---|---|---|
| `INFORM` | Passive notification | LOW |
| `WARN` | Advisory warning | MEDIUM |
| `CONSULT` | Request advice | MEDIUM |
| `VALIDATE` | Request audit | MEDIUM |
| `LEARN` | Share pattern | LOW |
| `BLOCK` | Hard stop | HIGH |
| `ESCALATE` | Raise to authority | CRITICAL |
| `REROUTE` | Redirect execution | MEDIUM |

---

## Project Structure

```
corpus/
├── api/             FastAPI routers
├── services/        Business logic
├── gravity/         Signal Gravity Engine
├── translation/     AI Translation Engine
├── memory/          Episodic Memory
├── policy/          Governance Engine
├── orchestration/   Multi-Product Orchestration
├── guardian/        Guardian Mode
├── observability/   Dashboard aggregation
├── security/        Auth + rate limiting
├── cli/             Click CLI
├── container.py     DI container
└── server.py        FastAPI app factory

sdk/python/corpus_sdk/   Python SDK
integrations/            Ready-made adapters
examples/                Runnable demos
docs/                    Full documentation
```

---

## Documentation

- [Quickstart](docs/QUICKSTART.md)
- [API Reference](docs/API_REFERENCE.md)
- [SDK Reference](docs/SDK_REFERENCE.md)
- [Integrations](docs/INTEGRATIONS.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Security](docs/SECURITY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Changelog](CHANGELOG.md)

---

## Design Principles

1. **Local-first** — works fully offline; Ollama is optional
2. **Async-native** — non-blocking throughout
3. **Graceful degradation** — products work without Corpus
4. **PolicyEngine is final authority** — Guardian cannot override policy
5. **Adapter isolation** — integrations import only `corpus_sdk`
6. **All decisions auditable** — gravity, policy, guardian all emit events

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run `pytest` before opening a PR.

## License

MIT
