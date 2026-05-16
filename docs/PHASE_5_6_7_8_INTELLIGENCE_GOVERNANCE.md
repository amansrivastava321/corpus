# Phases 5–8 — Intelligence & Governance

This document covers the four intelligence and governance phases that transform Corpus from a coordination runtime into a **self-aware, policy-enforced, translating, memory-equipped** multi-agent nervous system.

---

## Phase 5 — Signal Gravity Engine

### Overview

The **GravityEngine** computes the *effective importance* of every signal — combining its intrinsic weight with contextual factors to decide what action Corpus should recommend.

### Gravity Score

Every evaluation produces a `GravityScore`:

| Field | Type | Description |
|---|---|---|
| `score` | float | Effective weight after context adjustment |
| `action` | GravityAction | Recommended action |
| `explanation` | str | Human-readable reason |
| `confidence` | float | 0.0–1.0 certainty |
| `evidence` | list[str] | Audit trail of factors |
| `is_blocking` | bool | True if BLOCK or ESCALATE |
| `requires_checkpoint` | bool | True if DELAY/BLOCK/REROUTE/ESCALATE |

### Gravity Actions (ordered by severity)

| Action | Meaning |
|---|---|
| `IGNORE` | Signal is too low-weight to act on |
| `QUEUE` | Store for async processing |
| `INFORM` | Deliver passively |
| `WARN` | Deliver with a caution flag |
| `DELAY` | Pause execution, retry later |
| `BLOCK` | Hard stop — halt execution |
| `REROUTE` | Route through an alternate path |
| `ESCALATE` | Require human review |

### Rule Priority (highest → lowest)

| Signal Type | Severity | Action |
|---|---|---|
| BLOCK | CRITICAL | BLOCK |
| BLOCK | HIGH | BLOCK |
| ESCALATE | any | ESCALATE |
| INTERRUPT | CRITICAL | BLOCK |
| INTERRUPT | HIGH | DELAY |
| INTERRUPT | MEDIUM | DELAY |
| VALIDATE | CRITICAL | REROUTE |
| VALIDATE | HIGH | WARN |
| VALIDATE/CONSULT | MEDIUM/HIGH | WARN |
| BLOCK | MEDIUM | DELAY |
| INFORM/LEARN | LOW/MEDIUM | QUEUE |

### RiskContext

Pass a `RiskContext` to adjust the effective score:

```python
from corpus.gravity import GravityEngine, RiskContext

engine = GravityEngine()
score = engine.evaluate(signal, RiskContext(
    has_active_checkpoint=True,   # ×1.3
    source_trust=0.9,             # ×0.9
    target_online=True,           # ×1.0 (offline = ×0.7)
    historical_block_count=5,     # ×1.2 if > 3
))
```

### REST API

```http
POST /gravity/evaluate
{
  "signal": { "type": "BLOCK", "severity": "CRITICAL", ... },
  "has_active_checkpoint": false,
  "source_trust": 0.8
}
→ 200 {
  "action": "BLOCK",
  "score": 24.0,
  "is_blocking": true,
  "confidence": 1.0,
  "evidence": ["base_weight=30.00", "context_multiplier=0.80", ...]
}
```

### SDK

```python
g = client.gravity()
result = g.evaluate(signal_dict, has_active_checkpoint=True)
print(result.action)        # "BLOCK"
print(result.is_blocking)   # True
```

### Architecture

```
GravityEngine
├── apply_rules(signal_type, severity)  → GravityRule match
├── RiskContext.score_multiplier()      → context adjustment
└── GravityScore                        → final output

SignalPrioritizer
└── rank(signals, context)  → sorted list of (Signal, GravityScore)
```

---

## Phase 6 — AI Translation Engine

### Overview

The **Translator** converts signal payloads from one product's vocabulary to another's, preserving semantic intent. Translation is local-first: it always works without a network connection.

### Translation Pipeline

1. If `OLLAMA_URL` is configured → try LLM translation (Llama 3 by default)
2. If LLM unavailable or output invalid → **FallbackTranslator** (deterministic, rule-based)

### Product Profiles

Built-in profiles define each product's vocabulary and expected payload fields:

| Product | Vocabulary | Expected Fields |
|---|---|---|
| `anvil` | `audit→validate`, `violation→block`, `finding→warning` | `module, action, reason, severity` |
| `inspectra` | `task→audit_target`, `deploy→validate`, `block→violation` | `finding, rule, file, severity, recommendation` |
| `generic` | (none) | (none) |

New profiles can be added to `corpus/translation/product_profile.py`.

### REST API

```http
POST /translation/translate
{
  "source_product": "inspectra",
  "target_product": "anvil",
  "payload": {"finding": "SQL injection", "rule": "SEC-001"},
  "signal_type": "BLOCK",
  "severity": "CRITICAL"
}
→ 200 {
  "translated_payload": {"block": "SQL injection", "reason": "SEC-001", ...},
  "confidence": 0.75,
  "method": "fallback",
  "explanation": "Intent mapped 1 field(s): finding→warning",
  "warnings": ["Expected field 'module' could not be populated"]
}
```

### SDK

```python
t = client.translator()
result = t.translate("inspectra", "anvil", payload, signal_type="BLOCK", severity="CRITICAL")
print(result.translated_payload)
print(result.method)      # "llm" or "fallback"
print(result.confidence)  # 0.0–1.0
```

### Ollama (optional)

Set `CORPUS_OLLAMA_URL=http://localhost:11434` to enable LLM translation. Corpus falls back gracefully if Ollama is unreachable.

---

## Phase 7 — Episodic Memory & Learning

### Overview

The **MemoryService** captures every significant signal interaction as an *episode* — a structured record of what happened, what decisions were made, and what the outcome was. Patterns are mined from historical episodes.

### Episode Structure

```python
{
  "id": "ep-uuid",
  "signal_id": "sig-uuid",
  "signal_type": "BLOCK",
  "severity": "CRITICAL",
  "source_product": "inspectra",
  "target_product": "anvil",
  "payload": {...},
  "gravity_score": 24.0,
  "gravity_action": "BLOCK",
  "translation_method": "fallback",
  "policy_mode": "GUARDIAN",
  "clearance_decision": "BLOCK",
  "outcome": "BLOCKED",   # or RESOLVED, CANCELLED, PENDING
  "learning_notes": "...",
  "status": "CLOSED",
  "created_at": "...",
  "updated_at": "..."
}
```

### Pattern Mining

The `PatternMiner` detects recurring `(source, target, signal_type, outcome)` tuples across episodes. Patterns are stored in the `patterns` table and written to `artifacts/memory/patterns.json`.

### Recall Engine

The `RecallEngine` uses a keyword-based inverted index to retrieve relevant past episodes for a given query. This provides context enrichment without requiring external embedding services.

### Artifact Snapshots

Call `POST /memory/snapshot` to write the current memory state to:
- `artifacts/memory/episodes.json`
- `artifacts/memory/patterns.json`
- `artifacts/memory/learning_summary.json`

### REST API

```http
GET  /memory/episodes?product=anvil&status=CLOSED&limit=50
GET  /memory/episodes/{episode_id}
POST /memory/recall       { "query": "block authentication", "top_k": 5 }
POST /memory/mine-patterns
POST /memory/snapshot
```

### SDK

```python
m = client.memory()
episodes = m.list_episodes(product="anvil")
relevant = m.recall("block critical authentication", top_k=3)
patterns = m.mine_patterns()
m.snapshot()
```

---

## Phase 8 — Policy & Governance Engine

### Overview

The **PolicyEngine** controls who can do what to whom. It operates in one of three **governance modes**:

| Mode | Capabilities |
|---|---|
| `OBSERVER` | Record-only — no interventions, all signals pass |
| `ADVISOR` | Warn and delay — no hard blocks (BLOCK signals downgraded to WARN) |
| `GUARDIAN` | Full enforcement — can block, reroute, escalate based on rules |

### Trust Registry

Every product is assigned a trust level:

| Level | Numeric | Description |
|---|---|---|
| `UNTRUSTED` | 0.0 | Cannot emit blocking signals |
| `LOW` | 0.25 | Can emit INFORM/LEARN/CONSULT |
| `MEDIUM` | 0.50 | Can emit INTERRUPT, VALIDATE, BLOCK |
| `HIGH` | 0.75 | Full signal privileges |
| `TRUSTED` | 1.0 | Full privileges + higher governance weight |

### Default Policy

Out of the box, Corpus runs in `GUARDIAN` mode with `anvil` and `inspectra` at `HIGH` trust.

### Custom Policy

Policy can be loaded from a JSON config:

```json
{
  "mode": "GUARDIAN",
  "trust": {
    "anvil": "HIGH",
    "inspectra": "HIGH",
    "new_product": "MEDIUM"
  },
  "rules": [
    {
      "name": "no_critical_from_new_product",
      "source_product": "new_product",
      "allowed_signal_types": ["INFORM", "LEARN"],
      "min_trust_level": "MEDIUM",
      "max_severity": "HIGH"
    }
  ]
}
```

### REST API

```http
GET  /policy                         → current mode, trust levels, rules
POST /policy/reload                  → reload from default config
POST /policy/evaluate
  { "source_product": "inspectra", "target_product": "anvil",
    "signal_type": "BLOCK", "severity": "CRITICAL" }
→ { "authorized": true, "action_taken": "ALLOW", "mode": "GUARDIAN", ... }
```

### SDK

```python
p = client.policy()
current = p.get()
print(current["mode"])        # "GUARDIAN"

result = p.evaluate("inspectra", "anvil", "BLOCK", "CRITICAL")
print(result.authorized)      # True
print(result.action_taken)    # "ALLOW"

p.reload()
```

---

## Cross-Phase Integration Flow

When a signal is emitted, the full intelligence pipeline runs:

```
Signal emitted
    ↓
GravityEngine.evaluate()     → gravity score + action
    ↓
Translator.translate()       → adapted payload for target
    ↓
PolicyEngine.evaluate()      → authorization check
    ↓
ClearanceEngine (Phase 4)    → checkpoint governance
    ↓
RealtimeDispatcher           → WebSocket delivery
    ↓
MemoryService.record_episode() → persist to episodic memory
```

### Event Bus Integration

All four engines emit events:

| Event | Phase | Trigger |
|---|---|---|
| `GRAVITY_COMPUTED` | 5 | Signal evaluated by gravity engine |
| `SIGNAL_TRANSLATED` | 6 | Payload translated |
| `EPISODE_CREATED` | 7 | New episode recorded |
| `EPISODE_UPDATED` | 7 | Episode outcome updated |
| `PATTERN_MINED` | 7 | Pattern mining completed |
| `POLICY_LOADED` | 8 | Policy config loaded |
| `GOVERNANCE_ACTION_AUTHORIZED` | 8 | Signal authorized |
| `GOVERNANCE_ACTION_DENIED` | 8 | Signal denied |

---

## Architecture

```
CorpusContainer
├── GravityEngine              ← Phase 5: stateless signal evaluator
│   └── SignalPrioritizer      ← batch ranking
├── Translator                 ← Phase 6: vocabulary adapter
│   └── TranslationEngine      ← LLM or fallback
│       └── FallbackTranslator ← deterministic, no deps
├── MemoryService              ← Phase 7: episodic memory
│   ├── EpisodeStore           ← SQLite persistence
│   ├── EmbeddingIndex         ← keyword recall
│   ├── PatternMiner           ← recurring pattern detection
│   ├── RecallEngine           ← context retrieval
│   └── LearningArtifacts      ← JSON snapshot writer
└── PolicyEngine               ← Phase 8: governance enforcement
    ├── TrustRegistry          ← product → trust level
    ├── AuthorityResolver      ← per-action authority checks
    ├── GovernanceModes        ← mode capability table
    └── PolicyLoader           ← config reader
```

### Database Tables (Phase 7)

```sql
CREATE TABLE episodes (
    episode_id     TEXT PRIMARY KEY,
    source_product TEXT NOT NULL,
    target_product TEXT NOT NULL,
    signal_type    TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'OPEN',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    data           TEXT NOT NULL   -- JSON: full episode dict
);

CREATE TABLE patterns (
    pattern_id       TEXT PRIMARY KEY,
    pattern_type     TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    discovered_at    TEXT NOT NULL,
    data             TEXT NOT NULL   -- JSON: full pattern dict
);
```
