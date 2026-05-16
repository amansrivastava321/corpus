# Corpus Artifacts

Runtime state files persisted by the Corpus daemon.

| File | Description |
|---|---|
| `sample_signals.json` | Sample signals covering all 7 signal types (INFORM → ESCALATE) |
| `sample_products.json` | Sample Anvil + Inspectra product registrations |
| `signals.json` | Live signal store (written by runtime, gitignored in production) |
| `registered_products.json` | Live product registry (written by runtime) |
| `corpus_runtime_state.json` | Runtime heartbeat + health state |
