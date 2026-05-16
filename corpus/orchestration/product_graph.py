"""ProductGraph — tracks registered products and their capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProductNode:
    product_id: str
    product_name: str
    capabilities: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ProductDependency:
    source: str   # product_name
    target: str   # product_name
    relationship: str  # e.g. "depends_on", "audits", "monitors"


class ProductGraph:
    """
    In-memory registry of products and their declared capabilities.
    Capabilities are declared at registration time or updated via the API.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, ProductNode] = {}
        self._edges: list[ProductDependency] = []

    def upsert(self, product_id: str, product_name: str, capabilities: list[str]) -> ProductNode:
        node = ProductNode(
            product_id=product_id,
            product_name=product_name,
            capabilities=capabilities,
        )
        self._nodes[product_id] = node
        return node

    def remove(self, product_id: str) -> None:
        self._nodes.pop(product_id, None)

    def find_by_capability(self, capability: str) -> list[ProductNode]:
        return [n for n in self._nodes.values() if capability in n.capabilities]

    def find_by_name(self, name: str) -> ProductNode | None:
        for node in self._nodes.values():
            if node.product_name.lower() == name.lower():
                return node
        return None

    def add_dependency(self, source: str, target: str, relationship: str = "depends_on") -> None:
        self._edges.append(ProductDependency(source, target, relationship))

    def all_nodes(self) -> list[ProductNode]:
        return list(self._nodes.values())

    def all_capabilities(self) -> set[str]:
        caps: set[str] = set()
        for node in self._nodes.values():
            caps.update(node.capabilities)
        return caps

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {
                    "product_id": n.product_id,
                    "product_name": n.product_name,
                    "capabilities": n.capabilities,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "relationship": e.relationship}
                for e in self._edges
            ],
        }
