"""Example: Basic signal flow between two products.

Run Corpus first:
    corpus serve --db :memory:

Then run this script:
    python examples/basic_signal_flow.py
"""

from corpus_sdk import CorpusClient


def main() -> None:
    # Anvil connects and emits a BLOCK signal toward Inspectra
    anvil = CorpusClient(product_name="Anvil", base_url="http://localhost:8000")
    anvil.connect()

    inspectra = CorpusClient(product_name="Inspectra", base_url="http://localhost:8000")
    inspectra.connect()

    print("Emitting BLOCK signal from Anvil → Inspectra...")
    result = anvil.block(
        target="Inspectra",
        message="Critical vulnerability detected in auth module",
        payload={"file": "auth.py", "severity": "CRITICAL"},
    )
    print(f"Signal ID: {result.get('signal_id') or result.get('id', '?')}")

    print("\nInspectra polling for pending signals...")
    pending = inspectra.get_pending()
    for sig in pending.get("signals", []):
        print(f"  [{sig['signal_type']}] {sig['message']}")
        inspectra.acknowledge(sig["signal_id"])
        print(f"  Acknowledged signal {sig['signal_id']}")

    anvil.disconnect()
    inspectra.disconnect()
    print("\nDone.")


if __name__ == "__main__":
    main()
