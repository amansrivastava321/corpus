"""Example: Real-time signal listener via WebSocket.

Subscribes to the Corpus event stream and prints all incoming signals.

Run Corpus first:
    corpus serve --db :memory:

Then:
    python examples/realtime_listener.py
"""

import asyncio
import json


async def listen() -> None:
    try:
        import websockets  # type: ignore
    except ImportError:
        print("Install websockets: pip install websockets")
        return

    url = "ws://localhost:8000/ws/Listener"
    print(f"Connecting to {url}...")
    async with websockets.connect(url) as ws:
        print("Connected. Waiting for signals (Ctrl+C to stop)...\n")
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type", "?")
            if mtype == "signal":
                sig = msg.get("signal", {})
                print(
                    f"[{sig.get('signal_type', '?'):12}] "
                    f"{sig.get('source_product', '?')} → {sig.get('target_product', '?')}: "
                    f"{sig.get('message', '')[:60]}"
                )
            else:
                print(f"[{mtype}] {msg}")


if __name__ == "__main__":
    try:
        asyncio.run(listen())
    except KeyboardInterrupt:
        print("\nDisconnected.")
