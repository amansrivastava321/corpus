# Security

## Authentication

Corpus ships with optional API key authentication via the `X-API-Key` header.

**Disabled by default** so local development needs no configuration.

### Enable

```bash
export CORPUS_AUTH_ENABLED=true
export CORPUS_API_KEY=your-secret-key
corpus serve
```

All requests to protected endpoints must include:

```
X-API-Key: your-secret-key
```

Public endpoints that bypass auth:
- `GET /health`
- `GET /docs`
- `GET /openapi.json`
- `WS /ws/*`

### SDK usage with auth

```python
client = CorpusClient(
    product_name="Anvil",
    base_url="http://localhost:8000",
    headers={"X-API-Key": "your-secret-key"},
)
```

## Rate Limiting

Token-bucket rate limiting per client IP.

```bash
export CORPUS_RATE_LIMIT_ENABLED=true
export CORPUS_RATE_LIMIT_RPS=50   # requests per second
corpus serve
```

Requests exceeding the limit receive `429 Too Many Requests`.

## Trust Levels

Corpus maintains a TrustRegistry for each product:

| Level | Numeric | Can emit BLOCK/ESCALATE |
|-------|---------|------------------------|
| UNTRUSTED | 0.0 | No |
| LOW | 0.25 | No |
| MEDIUM | 0.50 | Yes |
| HIGH | 0.75 | Yes |
| TRUSTED | 1.0 | Yes |

Default trust: `MEDIUM`.

## Integration isolation

Integration adapters (`integrations/`) are architecturally isolated — they import only `corpus_sdk`, never internal `corpus.*` modules. This is verified by an AST-level test in `tests/integrations/test_integrations.py`.

## Reporting vulnerabilities

Please email security issues to the maintainers directly. Do not open public issues for security vulnerabilities.
