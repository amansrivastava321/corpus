"""ProductProfile — describes a product's communication style and vocabulary."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProductProfile:
    product_name: str
    # Human-readable description of how this product expresses intent
    style_description: str
    # Key vocabulary terms this product uses (used for intent mapping heuristics)
    vocabulary: dict[str, str] = field(default_factory=dict)
    # Fields this product expects in signal payloads
    expected_payload_fields: list[str] = field(default_factory=list)
    # System prompt fragment used when LLM translation is available
    system_hint: str = ""


ANVIL_PROFILE = ProductProfile(
    product_name="Anvil",
    style_description=(
        "Anvil is an AI developer orchestration tool. It communicates in terms of "
        "tasks, pipelines, commits, modules, and deployment stages. It expects "
        "structured action items with clear target paths and severity levels."
    ),
    vocabulary={
        "audit": "validate",
        "violation": "block",
        "finding": "warning",
        "security_issue": "block",
        "pattern": "learn",
        "recommendation": "consult",
    },
    expected_payload_fields=["module", "action", "reason", "severity"],
    system_hint="Translate the signal into Anvil's developer-orchestration vocabulary.",
)

INSPECTRA_PROFILE = ProductProfile(
    product_name="Inspectra",
    style_description=(
        "Inspectra is an autonomous audit infrastructure tool. It communicates in "
        "terms of findings, violations, severities, file paths, rules, and compliance "
        "frameworks. It expects structured audit reports with evidence."
    ),
    vocabulary={
        "task": "audit_target",
        "pipeline": "audit_scope",
        "deploy": "validate",
        "commit": "scan_target",
        "warning": "finding",
        "block": "violation",
    },
    expected_payload_fields=["finding", "rule", "file", "severity", "recommendation"],
    system_hint="Translate the signal into Inspectra's audit-and-compliance vocabulary.",
)

GENERIC_PROFILE = ProductProfile(
    product_name="generic",
    style_description="A generic autonomous product with no specific vocabulary constraints.",
    system_hint="Translate the signal into clear, unambiguous language.",
)

_REGISTRY: dict[str, ProductProfile] = {
    "anvil": ANVIL_PROFILE,
    "inspectra": INSPECTRA_PROFILE,
}


def get_profile(product_name: str) -> ProductProfile:
    return _REGISTRY.get(product_name.lower(), GENERIC_PROFILE)
