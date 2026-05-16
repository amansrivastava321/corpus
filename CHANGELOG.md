# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-05-16

### Added

**Core runtime (Phases 0–4)**
- FastAPI daemon with aiosqlite persistence
- Product registry with heartbeat presence tracking
- Signal routing engine (INFORM, WARN, BLOCK, ESCALATE, CONSULT, LEARN, VALIDATE, REROUTE)
- Python SDK (`corpus_sdk`) with typed signal methods and InProcessTransport for testing
- Real-time WebSocket signal delivery
- Interrupt & Checkpoint Engine with pre-deploy clearance and audit trail

**Intelligence layer (Phases 5–8)**
- Signal Gravity Engine: weighted risk scoring, GravityAction routing (IGNORE → ESCALATE)
- AI Translation Engine: Ollama LLM with deterministic FallbackTranslator
- Episodic Memory: SQLite-backed episode store, pattern mining, learning artifacts
- Policy & Governance Engine: OBSERVER / ADVISOR / GUARDIAN modes, TrustRegistry, PolicyRules

**Coordination layer (Phases 9–10)**
- Multi-Product Orchestration: workflow engine, coordination planner, synthesis engine
- Guardian Mode: proactive risk prediction, intervention planning, adaptive thresholds

**Operations (Phases 11–12)**
- Observability Dashboard: read-only REST aggregation across all subsystems
- Production hardening: optional API key auth, per-IP rate limiting, Docker support

**Integrations & release (Phases 13–14)**
- Integration adapters: Anvil, Inspectra, Graphify, GitHub Actions CI, GitHub Webhooks
- Click-based CLI: `corpus serve`, `corpus doctor`, `corpus products list`, `corpus signals emit`, `corpus signals pending`, `corpus checkpoints list`, `corpus policy show`, `corpus guardian status`, `corpus dashboard summary`, `corpus export`, `corpus import`
- 369 tests covering all phases
- Full documentation: API reference, SDK reference, quickstart, deployment, security

---

## [Unreleased]

See [ROADMAP.md](docs/ROADMAP.md) for planned features.
