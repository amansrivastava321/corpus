"""
Generate JSON Schema contract files from Pydantic model definitions.

Run from the project root:
    python -m corpus.contracts.generate_contracts
"""

import json
from pathlib import Path

CONTRACTS_DIR = Path(__file__).parent


def generate_contracts() -> None:
    from corpus.schemas.checkpoint import Checkpoint
    from corpus.schemas.decision import ClearanceDecision
    from corpus.schemas.episode import Episode
    from corpus.schemas.product import ProductHeartbeat, ProductRegistration
    from corpus.schemas.signal import Signal

    schemas = {
        "signal": Signal,
        "product_registration": ProductRegistration,
        "product_heartbeat": ProductHeartbeat,
        "episode": Episode,
        "checkpoint": Checkpoint,
        "clearance_decision": ClearanceDecision,
    }

    for name, model in schemas.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://corpus.dev/schemas/{name}.json"
        output_path = CONTRACTS_DIR / f"{name}.schema.json"
        with open(output_path, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Generated: {output_path}")


if __name__ == "__main__":
    generate_contracts()
