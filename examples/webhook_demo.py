"""Example: GitHub webhook → Corpus signal bridge.

Shows how the WebhookCorpusIntegration translates GitHub events
into Corpus signals without ever touching Corpus internals.

Run Corpus first:
    corpus serve --db :memory:
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from corpus_sdk import CorpusClient
from corpus_sdk.transport import InProcessTransport  # type: ignore


def main() -> None:
    from integrations.webhook.webhook_integration import WebhookCorpusIntegration

    # In a real deployment you'd pass base_url="http://localhost:8000"
    # Here we use in-process transport for the demo
    print("Webhook integration demo")

    integration = WebhookCorpusIntegration()

    # Show default signal map
    from integrations.webhook.webhook_integration import _DEFAULT_SIGNAL_MAP
    print("\nDefault event → signal mappings:")
    for event, (sig_type, severity) in list(_DEFAULT_SIGNAL_MAP.items())[:6]:
        print(f"  {event:<35} → {sig_type} [{severity}]")

    # Add a custom mapping
    integration.add_mapping("deployment_created", "INFORM", "LOW")
    print("\nAdded custom mapping: deployment_created → INFORM [LOW]")

    print("\nDone. In production, call integration.handle_event(event_type, payload)")
    print("after calling integration.connect() with your Corpus URL.")


if __name__ == "__main__":
    main()
