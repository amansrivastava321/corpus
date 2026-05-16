# Roadmap

## Released (v0.1.0)

- **Phase 0** — Project setup, schema design, core models
- **Phase 1** — FastAPI daemon, SQLite persistence, product registry, signal routing
- **Phase 2** — Python SDK (`corpus_sdk`), connection management, typed signal methods
- **Phase 3** — Real-time WebSocket signal delivery
- **Phase 4** — Interrupt & Checkpoint Engine (pre-deploy clearance, blocking signals)
- **Phase 5** — Signal Gravity Engine (weighted risk scoring, GravityAction routing)
- **Phase 6** — AI Translation Engine (Ollama-backed, deterministic fallback)
- **Phase 7** — Episodic Memory & Learning (SQLite episodes, pattern mining)
- **Phase 8** — Policy & Governance Engine (OBSERVER / ADVISOR / GUARDIAN modes)
- **Phase 9** — Multi-Product Orchestration (workflows, synthesis engine)
- **Phase 10** — Guardian Mode (proactive intervention, adaptive thresholds)
- **Phase 11** — Observability Dashboard (read-only REST aggregation)
- **Phase 12** — Production Hardening (auth, rate limiting, Docker, config)
- **Phase 13** — Real Integration Adapters (Anvil, Inspectra, Graphify, CI, Webhook)
- **Phase 14** — Packaging, CLI, open-source release readiness

## Planned (v0.2.0)

- **Persistent vector memory** — replace keyword inverted index with a local embedding store (e.g., ChromaDB or SQLite-vec)
- **LLM-backed synthesis** — use Ollama/OpenAI to generate natural-language rationale for workflow decisions
- **Streaming WebSocket signals** — push signals to registered listeners in real time (beyond current pull model)
- **Corpus-to-Corpus federation** — allow Corpus instances to signal each other across trust boundaries
- **Multi-tenant namespacing** — product scoping by namespace/team

## Planned (v0.3.0)

- **Postgres backend** — drop-in alternative to SQLite for high-throughput deployments
- **gRPC transport** — alternative to HTTP for low-latency product communication
- **Audit log export** — structured export to SIEM / object storage
- **Web UI** — React dashboard for the observability backend
- **Helm chart** — Kubernetes deployment out of the box
