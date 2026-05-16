"""PromptRegistry — system/user prompt templates for LLM-based translation."""

from __future__ import annotations


_SYSTEM_TEMPLATE = """\
You are Corpus, an AI-native coordination runtime. Your task is to translate a signal payload
from one autonomous product's vocabulary to another's without changing the semantic intent.

Source product: {source_product}
Source style: {source_style}

Target product: {target_product}
Target style: {target_style}

Rules:
- Preserve all factual information; do not hallucinate new facts
- Output ONLY a JSON object — no prose
- Use the target product's vocabulary and field names
- If a field cannot be meaningfully translated, omit it
"""

_USER_TEMPLATE = """\
Signal type: {signal_type}
Severity: {severity}

Original payload (JSON):
{payload_json}

Translate this payload to {target_product}'s vocabulary. Output a JSON object only.
"""


def build_prompt(
    source_product: str,
    source_style: str,
    target_product: str,
    target_style: str,
    signal_type: str,
    severity: str,
    payload_json: str,
) -> tuple[str, str]:
    system = _SYSTEM_TEMPLATE.format(
        source_product=source_product,
        source_style=source_style,
        target_product=target_product,
        target_style=target_style,
    )
    user = _USER_TEMPLATE.format(
        signal_type=signal_type,
        severity=severity,
        payload_json=payload_json,
        target_product=target_product,
    )
    return system, user
