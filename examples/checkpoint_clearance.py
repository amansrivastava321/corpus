"""Example: Deployment checkpoint with clearance request.

Shows how a CI system blocks a deploy and Anvil requests clearance.

Run Corpus first:
    corpus serve --db :memory:
"""

import httpx


BASE = "http://localhost:8000"


def main() -> None:
    with httpx.Client(base_url=BASE) as client:
        # Register the products
        client.post("/products/register", json={
            "name": "CI",
            "capabilities": ["ci_status"],
        }).raise_for_status()
        client.post("/products/register", json={
            "name": "Anvil",
            "capabilities": ["task_management"],
        }).raise_for_status()

        # CI emits a BLOCK signal, which triggers a checkpoint
        print("CI emitting BLOCK signal...")
        resp = client.post("/signals", json={
            "source_product": "CI",
            "target_product": "Anvil",
            "signal_type": "BLOCK",
            "severity": "HIGH",
            "message": "Build failed — deployment blocked",
            "payload": {"run_id": "run-42", "failures": 3},
        })
        resp.raise_for_status()
        signal = resp.json()
        print(f"Signal created: {signal.get('signal_id') or signal.get('id', '?')}")

        # List waiting checkpoints
        print("\nListing checkpoints waiting for clearance...")
        resp = client.get("/checkpoints?status=WAITING_CLEARANCE")
        resp.raise_for_status()
        checkpoints = resp.json().get("checkpoints", [])
        for cp in checkpoints:
            print(f"  Checkpoint {cp['checkpoint_id']}: {cp['reason'][:60]}")

            # Request pre-deploy clearance
            print(f"  Requesting clearance on {cp['checkpoint_id']}...")
            client.post(f"/checkpoints/{cp['checkpoint_id']}/approve").raise_for_status()
            print("  Clearance granted.")

    print("\nDone.")


if __name__ == "__main__":
    main()
