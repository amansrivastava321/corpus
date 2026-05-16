# Deployment

## Docker

```bash
docker build -t corpus:latest .
docker run -p 8000:8000 -v /data/corpus:/data corpus:latest \
  --db /data/corpus.db
```

### Docker Compose

```yaml
version: "3.9"
services:
  corpus:
    image: corpus:latest
    ports:
      - "8000:8000"
    environment:
      CORPUS_DB_PATH: /data/corpus.db
      CORPUS_AUTH_ENABLED: "true"
      CORPUS_API_KEY: "your-secret-key"
    volumes:
      - corpus_data:/data

volumes:
  corpus_data:
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CORPUS_HOST` | `0.0.0.0` | Bind host |
| `CORPUS_PORT` | `8000` | Bind port |
| `CORPUS_DB_PATH` | `corpus.db` | SQLite database path |
| `CORPUS_LOG_LEVEL` | `INFO` | Log level |
| `CORPUS_AUTH_ENABLED` | `false` | Enable API key auth |
| `CORPUS_API_KEY` | _(none)_ | Required key when auth enabled |
| `CORPUS_RATE_LIMIT_ENABLED` | `false` | Enable rate limiting |
| `CORPUS_RATE_LIMIT_RPS` | `100` | Requests per second per IP |
| `CORPUS_URL` | `http://localhost:8000` | Used by CLI commands |

## Production checklist

- [ ] Set `CORPUS_AUTH_ENABLED=true` and a strong `CORPUS_API_KEY`
- [ ] Set `CORPUS_RATE_LIMIT_ENABLED=true`
- [ ] Use a persistent `CORPUS_DB_PATH` (not `:memory:`)
- [ ] Place behind a TLS-terminating reverse proxy (nginx, Caddy)
- [ ] Mount the database path as a persistent volume
- [ ] Set `CORPUS_LOG_LEVEL=WARNING` for lower noise
- [ ] Configure alerting on `GET /health` returning non-`ok`

## Scaling

Corpus uses a SQLite backend and is designed for single-node deployment.
For higher throughput, run one Corpus instance per trust boundary / team.
Corpus instances can signal each other like any other product.
