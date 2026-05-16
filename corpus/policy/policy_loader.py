"""PolicyLoader — loads policy configuration from a dict/JSON/YAML source."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from corpus.policy.policy_models import GovernanceMode, PolicyRule, TrustLevel
from corpus.policy.trust_registry import TrustRegistry

_log = logging.getLogger(__name__)

_DEFAULT_POLICY: dict = {
    "mode": "GUARDIAN",
    "trust": {
        "anvil": "HIGH",
        "inspectra": "HIGH",
    },
    "rules": [],
}


class PolicyLoader:
    """Loads and validates policy configuration."""

    def load_dict(self, config: dict) -> tuple[GovernanceMode, TrustRegistry, list[PolicyRule]]:
        mode = GovernanceMode(config.get("mode", "GUARDIAN"))

        registry = TrustRegistry()
        for product, level in config.get("trust", {}).items():
            registry.set(product, TrustLevel(level))

        rules: list[PolicyRule] = []
        for r in config.get("rules", []):
            rules.append(
                PolicyRule(
                    name=r.get("name", "unnamed"),
                    source_product=r.get("source_product"),
                    target_product=r.get("target_product"),
                    allowed_signal_types=r.get("allowed_signal_types", []),
                    min_trust_level=TrustLevel(r.get("min_trust_level", "LOW")),
                    max_severity=r.get("max_severity"),
                    requires_mode=GovernanceMode(r.get("requires_mode", "OBSERVER")),
                    description=r.get("description", ""),
                )
            )

        return mode, registry, rules

    def load_file(self, path: Path) -> tuple[GovernanceMode, TrustRegistry, list[PolicyRule]]:
        try:
            text = path.read_text()
            config = json.loads(text)
            return self.load_dict(config)
        except FileNotFoundError:
            _log.info("policy_file_not_found", extra={"path": str(path)})
            return self.load_dict(_DEFAULT_POLICY)
        except Exception as exc:
            _log.warning("policy_load_error", extra={"path": str(path), "error": str(exc)})
            return self.load_dict(_DEFAULT_POLICY)

    def default(self) -> tuple[GovernanceMode, TrustRegistry, list[PolicyRule]]:
        return self.load_dict(_DEFAULT_POLICY)
