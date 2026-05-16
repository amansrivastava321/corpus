"""Example: Guardian mode — proactive intervention on risky signals.

Guardian evaluates every incoming signal against risk predictions
and the active policy. This demo shows how it intervenes on a
CRITICAL BLOCK signal.

Run Corpus first:
    corpus serve --db :memory:
"""

import httpx


BASE = "http://localhost:8000"


def main() -> None:
    with httpx.Client(base_url=BASE) as client:
        # Check guardian status
        print("Guardian status:")
        gs = client.get("/guardian/status")
        gs.raise_for_status()
        print(f"  mode: {gs.json().get('mode', '?')}")

        # Register products
        for name in ("SecurityScanner", "Anvil"):
            client.post("/products/register", json={"name": name, "capabilities": []}).raise_for_status()

        # Emit a CRITICAL ESCALATE signal — Guardian should intervene
        print("\nEmitting CRITICAL ESCALATE signal...")
        resp = client.post("/signals", json={
            "source_product": "SecurityScanner",
            "target_product": "Anvil",
            "signal_type": "ESCALATE",
            "severity": "CRITICAL",
            "message": "CVE-2024-9999 detected in production dependency",
            "payload": {"cve": "CVE-2024-9999", "package": "requests", "version": "<2.32.0"},
        })
        resp.raise_for_status()
        print(f"  Signal: {resp.json().get('signal_id') or resp.json().get('id', '?')}")

        # View interventions
        print("\nGuardian interventions:")
        iv = client.get("/guardian/interventions")
        iv.raise_for_status()
        for item in iv.json().get("interventions", [])[:5]:
            print(f"  [{item.get('action')}] {item.get('reason', '')[:70]}")

    print("\nDone.")


if __name__ == "__main__":
    main()
