"""Example: Multi-product orchestration workflow.

Corpus orchestrates a deploy decision by consulting CI, Graphify, and Inspectra
before synthesizing a final ALLOW/BLOCK decision.

Run Corpus first:
    corpus serve --db :memory:
"""

import httpx
import time


BASE = "http://localhost:8000"


def main() -> None:
    with httpx.Client(base_url=BASE) as client:
        # Register participating products
        for product in [
            {"name": "Anvil", "capabilities": ["task_management", "deploy"]},
            {"name": "CI", "capabilities": ["ci_status", "test_history"]},
            {"name": "Graphify", "capabilities": ["code_graph", "impact_analysis"]},
            {"name": "Inspectra", "capabilities": ["security_scan", "vulnerability_detection"]},
        ]:
            client.post("/products/register", json=product).raise_for_status()

        # Create a workflow: Anvil wants to deploy, asks CI + Graphify to validate
        print("Creating orchestration workflow...")
        resp = client.post("/orchestration/workflows", json={
            "initiating_product": "Anvil",
            "action": "deploy auth-service v2.4.1",
            "required_capabilities": ["ci_status", "impact_analysis"],
            "context": {"branch": "main", "commit": "abc1234"},
        })
        resp.raise_for_status()
        workflow = resp.json()
        wf_id = workflow["id"]
        print(f"  Workflow ID: {wf_id}")

        # Start the workflow
        print("Starting workflow...")
        resp = client.post(f"/orchestration/workflows/{wf_id}/start")
        resp.raise_for_status()
        result = resp.json()
        print(f"  Status: {result.get('status')}")
        print(f"  Decision: {result.get('synthesized_decision', {}).get('decision', '?')}")
        print(f"  Rationale: {result.get('synthesized_decision', {}).get('rationale', '?')}")

    print("\nDone.")


if __name__ == "__main__":
    main()
