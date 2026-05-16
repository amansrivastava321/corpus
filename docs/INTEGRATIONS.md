# Integrations

Corpus ships with ready-made integration adapters for common tools. Each adapter wraps `CorpusClient` and translates tool-native events into Corpus signals.

## Anvil

Task management integration.

```python
from integrations.anvil.anvil_integration import AnvilCorpusIntegration

anvil = AnvilCorpusIntegration(corpus_url="http://localhost:8000")
anvil.connect()

anvil.task_started("refactor auth module", "auth.py")
anvil.request_pre_deploy_clearance("v2.4.1", target="CI")
anvil.signal_audit_request("Why was this signal blocked?")

anvil.disconnect()
```

## Inspectra

Security scanning integration.

```python
from integrations.inspectra.inspectra_integration import InspectraCorpusIntegration

inspectra = InspectraCorpusIntegration(corpus_url="http://localhost:8000")
inspectra.connect()

inspectra.report_critical_finding("CVE-2024-9999", "auth.py", target="Anvil")
inspectra.report_warning("Deprecated dependency", "requirements.txt")
inspectra.share_pattern({"pattern": "SQL injection", "locations": ["db.py"]})

inspectra.disconnect()
```

## Graphify / Nexus

Code graph and dependency impact analysis.

```python
from integrations.graphify.graphify_integration import GraphifyCorpusIntegration

graphify = GraphifyCorpusIntegration(corpus_url="http://localhost:8000")
graphify.connect()

graphify.report_impact("auth.py", ["user_service.py", "api.py"], risk_level="HIGH")
graphify.share_dependency_graph({"nodes": [...], "edges": [...]})

graphify.disconnect()
```

**Capabilities:** `code_graph`, `impact_analysis`

## GitHub Actions / CI

```python
from integrations.github_actions.ci_integration import CICorpusIntegration

ci = CICorpusIntegration(corpus_url="http://localhost:8000")
ci.connect()

ci.report_ci_failure("my-org/my-repo", "main", "https://github.com/.../runs/42")
ci.report_ci_success("my-org/my-repo", "main")
ci.share_test_history("my-org/my-repo", history=[...])

ci.disconnect()
```

**Capabilities:** `ci_status`, `test_history`

## GitHub Webhooks

Maps GitHub webhook event types to Corpus signals automatically.

```python
from integrations.webhook.webhook_integration import WebhookCorpusIntegration

integration = WebhookCorpusIntegration(corpus_url="http://localhost:8000")
integration.connect()

# In your Flask/FastAPI webhook handler:
@app.post("/webhook")
async def handle(request):
    event_type = request.headers.get("X-GitHub-Event")
    payload = await request.json()
    result = integration.handle_event(event_type, payload)
    return {"ok": True}
```

### Default event mappings

| GitHub Event | Signal Type | Severity |
|---|---|---|
| `push` | INFORM | LOW |
| `pull_request.opened` | INFORM | LOW |
| `pull_request.closed` | INFORM | LOW |
| `deployment_status.failure` | BLOCK | HIGH |
| `deployment_status.success` | INFORM | LOW |
| `check_run.failure` | WARN | MEDIUM |
| `security_advisory` | ESCALATE | CRITICAL |
| `repository_vulnerability_alert` | BLOCK | HIGH |

Add custom mappings:

```python
integration.add_mapping("deployment_created", "INFORM", "LOW")
```

## Writing your own integration

1. Create `integrations/your_tool/your_tool_integration.py`
2. Import only `corpus_sdk` — never `corpus.*` internals
3. Declare `CAPABILITIES: list[str]`
4. Implement `connect()` / `disconnect()`
5. Wrap your tool events into `self._client.block()`, `.inform()`, etc.

```python
from corpus_sdk import CorpusClient

class YourToolCorpusIntegration:
    CAPABILITIES = ["your_capability"]

    def __init__(self, corpus_url: str = "http://localhost:8000") -> None:
        self._client = CorpusClient(product_name="YourTool", base_url=corpus_url)
        self._connected = False

    def connect(self) -> None:
        self._client.connect()
        self._connected = True

    def on_something_happened(self, data: dict) -> dict:
        return self._client.inform(
            target="*",
            message="Something happened",
            payload=data,
        )

    def disconnect(self) -> None:
        if self._connected:
            self._client.disconnect()
            self._connected = False
```
