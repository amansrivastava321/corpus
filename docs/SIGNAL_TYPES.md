# Corpus Signal Type Reference

Each signal must declare a `type` that governs its routing intent, delivery priority,
and gravity multiplier. The `severity` field (LOW → CRITICAL) is orthogonal to type
and scales the overall gravity weight.

---

## INFORM
**Gravity multiplier**: 0.5 | **Requires ACK**: optional | **Broadcast**: allowed

Passive notification. The emitting product shares state but expects no action from the receiver.

Use when a product wants to update others about what it is doing without requiring a response.

**Example**:
```json
{
  "type": "INFORM",
  "severity": "LOW",
  "source_product": "anvil",
  "target_product": "inspectra",
  "payload": {
    "message": "Starting analysis on auth module",
    "files": ["auth/login.py", "auth/session.py"]
  }
}
```

---

## CONSULT
**Gravity multiplier**: 1.0 | **Requires ACK**: yes | **Broadcast**: no

Request for advice or input. The emitting product is seeking guidance before proceeding.
A response signal is expected from the target.

Use when a product needs a second opinion or risk assessment before taking an action.

**Example**:
```json
{
  "type": "CONSULT",
  "severity": "MEDIUM",
  "source_product": "anvil",
  "target_product": "inspectra",
  "payload": {
    "question": "Is it safe to refactor session token generation?",
    "context": { "planned_change": "Replace uuid4 with signed JWTs" }
  }
}
```

---

## INTERRUPT
**Gravity multiplier**: 2.0 | **Requires ACK**: yes | **Broadcast**: no

Request to pause the target product's current operation. The emitting product believes
the operation should not continue until the interrupt is resolved. Unlike BLOCK, an
INTERRUPT can be overridden by the target with justification.

Use when a product detects a risk that warrants a pause but not necessarily a full stop.

**Example**:
```json
{
  "type": "INTERRUPT",
  "severity": "HIGH",
  "source_product": "inspectra",
  "target_product": "anvil",
  "payload": {
    "reason": "SQL injection risk detected in auth/login.py:47",
    "recommendation": "Parameterise query before executing"
  }
}
```

---

## BLOCK
**Gravity multiplier**: 3.0 | **Requires ACK**: yes | **Broadcast**: no

Hard stop. The target product must not proceed until the block is explicitly cleared
by Corpus. Blocks cannot be overridden unilaterally — they require a `ClearanceDecision`
of type `ALLOW` or `REROUTE`.

Use for critical security violations, compliance failures, or states that would cause
irreversible harm.

**Example**:
```json
{
  "type": "BLOCK",
  "severity": "CRITICAL",
  "source_product": "inspectra",
  "target_product": "anvil",
  "payload": {
    "reason": "Hardcoded secret key found in auth/config.py:12. CVSS 9.1.",
    "required_action": "Rotate secret, move to environment variable"
  }
}
```

---

## VALIDATE
**Gravity multiplier**: 1.5 | **Requires ACK**: yes | **Broadcast**: no

Request for audit or validation of a specific artifact (code diff, config, deployment plan).
The target is expected to perform the requested validation and return a structured result.

Use when a product wants a formal sign-off on an artifact before acting on it.

**Example**:
```json
{
  "type": "VALIDATE",
  "severity": "MEDIUM",
  "source_product": "anvil",
  "target_product": "inspectra",
  "payload": {
    "artifact_type": "code_diff",
    "artifact_ref": "pr/anvil/branch/fix-auth-sqli",
    "validation_scope": ["security", "correctness"]
  }
}
```

---

## LEARN
**Gravity multiplier**: 0.7 | **Requires ACK**: no | **Broadcast**: allowed

Share a learned pattern, observed behaviour, or insight with other products. LEARN
signals build the shared knowledge graph that enables Corpus to become predictive.

Use to propagate patterns discovered during audits, executions, or failure analysis.

**Example**:
```json
{
  "type": "LEARN",
  "severity": "LOW",
  "source_product": "inspectra",
  "target_product": null,
  "metadata": { "broadcast": true },
  "payload": {
    "pattern": "hardcoded_secret_in_config",
    "frequency": 3,
    "suggested_fix": "Use os.environ.get() or a secrets manager"
  }
}
```

---

## ESCALATE
**Gravity multiplier**: 2.5 | **Requires ACK**: yes | **Broadcast**: allowed

Raise an unresolved situation to a higher authority — either another product with
`ORCHESTRATE` capability, or human oversight. Typically emitted by Corpus itself
when an interrupt or block is not acknowledged within the TTL window.

Use when automated resolution has failed and a human or senior agent must intervene.

**Example**:
```json
{
  "type": "ESCALATE",
  "severity": "CRITICAL",
  "source_product": "corpus",
  "target_product": null,
  "metadata": { "broadcast": true },
  "payload": {
    "reason": "CRITICAL BLOCK unacknowledged for > 10 minutes",
    "escalation_level": "HUMAN_OVERSIGHT",
    "unacked_signal_ids": ["..."]
  }
}
```

---

## Gravity Weight Table

| Type \ Severity | LOW | MEDIUM | HIGH | CRITICAL |
|---|---|---|---|---|
| INFORM | **0.5** | 1.25 | 2.5 | 5.0 |
| LEARN | 0.7 | 1.75 | 3.5 | 7.0 |
| CONSULT | 1.0 | 2.5 | 5.0 | 10.0 |
| VALIDATE | 1.5 | 3.75 | 7.5 | 15.0 |
| INTERRUPT | 2.0 | 5.0 | 10.0 | 20.0 |
| ESCALATE | 2.5 | 6.25 | 12.5 | 25.0 |
| BLOCK | 3.0 | 7.5 | 15.0 | **30.0** |

A `CRITICAL BLOCK` (gravity 30.0) triggers immediate interrupt routing with no queuing delay.
