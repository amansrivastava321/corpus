"""TrustRegistry — maps product names to trust levels."""

from __future__ import annotations

from corpus.policy.policy_models import TrustLevel


class TrustRegistry:
    """
    In-memory trust registry. Products not explicitly registered get MEDIUM trust.
    Load from policy config via PolicyLoader.
    """

    def __init__(self) -> None:
        self._levels: dict[str, TrustLevel] = {}

    def set(self, product_name: str, level: TrustLevel) -> None:
        self._levels[product_name.lower()] = level

    def get(self, product_name: str) -> TrustLevel:
        return self._levels.get(product_name.lower(), TrustLevel.MEDIUM)

    def numeric(self, product_name: str) -> float:
        return self.get(product_name).numeric()

    def as_dict(self) -> dict[str, str]:
        return {name: level.value for name, level in self._levels.items()}
