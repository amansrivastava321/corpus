"""
Phase 3 — WebSocket real-time bus tests.

All tests use Starlette's synchronous TestClient.websocket_connect() so no
async test infrastructure is required.  The ASGI event loop runs in a
background thread managed by the TestClient.

Test structure:
  TestWebSocketConnect         — connection lifecycle
  TestPresenceTracking         — ONLINE / OFFLINE / STALE state
  TestHeartbeat                — heartbeat messages
  TestRealtimeSignalDelivery   — push on connect and on emit
  TestWebSocketAck             — ACK via WebSocket
  TestBroadcastRealtime        — broadcast to multiple connected products
  TestOfflineQueueFallback     — REST queue when product is offline
  TestPresenceEndpoints        — GET /presence REST endpoints
"""

import threading

import pytest
from fastapi.testclient import TestClient

from corpus.server import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server():
    with TestClient(create_app(db_path=":memory:")) as tc:
        yield tc


def _register(server, name: str, version: str = "1.0.0") -> str:
    """Register a product and return its product_id."""
    resp = server.post(
        "/products/register",
        json={"name": name, "version": version},
    )
    assert resp.status_code == 201
    return resp.json()["product_id"]


# ---------------------------------------------------------------------------
# TestWebSocketConnect
# ---------------------------------------------------------------------------


class TestWebSocketConnect:
    def test_connect_sends_connected_message(self, server):
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            msg = ws.receive_json()
        assert msg["message_type"] == "CONNECTED"
        assert msg["product_id"] == pid
        assert msg["product_name"] == "Anvil"

    def test_connect_reports_zero_pending(self, server):
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            msg = ws.receive_json()
        assert msg["pending_count"] == 0

    def test_connect_unregistered_product_rejected(self, server):
        with pytest.raises(Exception):
            with server.websocket_connect("/ws/products/ghost-id") as ws:
                ws.receive_json()

    def test_disconnect_marks_product_offline(self, server):
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()  # CONNECTED
        # After context exit, product is offline
        presence = server.get(f"/presence/{pid}").json()
        assert presence["status"] == "OFFLINE"
        assert presence["connected"] is False

    def test_connect_marks_product_online(self, server):
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()  # CONNECTED
            presence = server.get(f"/presence/{pid}").json()
            assert presence["status"] == "ONLINE"
            assert presence["connected"] is True


# ---------------------------------------------------------------------------
# TestPresenceTracking
# ---------------------------------------------------------------------------


class TestPresenceTracking:
    def test_presence_unknown_before_ws_connect(self, server):
        pid = _register(server, "Anvil")
        resp = server.get(f"/presence/{pid}")
        assert resp.status_code == 404

    def test_presence_online_while_connected(self, server):
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()
            data = server.get(f"/presence/{pid}").json()
        assert data["status"] == "ONLINE"

    def test_presence_offline_after_disconnect(self, server):
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()
        data = server.get(f"/presence/{pid}").json()
        assert data["status"] == "OFFLINE"

    def test_presence_lists_all(self, server):
        anvil_id = _register(server, "Anvil")
        inspectra_id = _register(server, "Inspectra")
        with server.websocket_connect(f"/ws/products/{anvil_id}") as ws1:
            ws1.receive_json()
            with server.websocket_connect(f"/ws/products/{inspectra_id}") as ws2:
                ws2.receive_json()
                # Receive PRESENCE_UPDATE from Inspectra connect
                _ = ws1.receive_json()
                all_presence = server.get("/presence").json()
        names = {p["product_name"] for p in all_presence}
        assert "Anvil" in names
        assert "Inspectra" in names

    def test_stale_detection(self, server):
        from corpus.websocket.presence_tracker import PresenceStatus
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()
            container = server.app.state.container
            presence = container.presence_tracker.get(pid)
            # Manually set last_seen far in the past to simulate stale
            from datetime import datetime, timezone, timedelta
            presence.last_seen = datetime.now(timezone.utc) - timedelta(seconds=120)
            # Run stale check directly (no sleep needed)
            import asyncio
            loop = asyncio.new_event_loop()
            changed = loop.run_until_complete(container.heartbeat_monitor.check_stale())
            loop.close()
            assert pid in changed
            p = container.presence_tracker.get(pid)
            assert p.status == PresenceStatus.STALE

    def test_offline_after_stale_timeout(self, server):
        from corpus.websocket.presence_tracker import PresenceStatus
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()
            container = server.app.state.container
            presence = container.presence_tracker.get(pid)
            # Set stale first
            from datetime import datetime, timezone, timedelta
            presence.last_seen = datetime.now(timezone.utc) - timedelta(seconds=120)
            container.presence_tracker.mark_stale(pid)
            # Second check should move to OFFLINE
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(container.heartbeat_monitor.check_stale())
            loop.close()
            p = container.presence_tracker.get(pid)
            assert p.status == PresenceStatus.OFFLINE


# ---------------------------------------------------------------------------
# TestHeartbeat
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_heartbeat_receives_ack(self, server):
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()  # CONNECTED
            ws.send_json({"message_type": "HEARTBEAT"})
            ack = ws.receive_json()
        assert ack["message_type"] == "HEARTBEAT_ACK"
        assert "server_time" in ack

    def test_heartbeat_updates_last_seen(self, server):
        from datetime import datetime, timezone, timedelta

        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()  # CONNECTED
            container = server.app.state.container
            presence = container.presence_tracker.get(pid)
            # Set last_seen to past
            presence.last_seen = datetime.now(timezone.utc) - timedelta(seconds=60)
            old_seen = presence.last_seen
            ws.send_json({"message_type": "HEARTBEAT"})
            ws.receive_json()  # HEARTBEAT_ACK
            new_seen = container.presence_tracker.get(pid).last_seen
        assert new_seen > old_seen

    def test_heartbeat_clears_stale(self, server):
        from corpus.websocket.presence_tracker import PresenceStatus
        from datetime import datetime, timezone, timedelta

        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()  # CONNECTED
            container = server.app.state.container
            # Force stale
            container.presence_tracker.mark_stale(pid)
            assert container.presence_tracker.get(pid).status == PresenceStatus.STALE
            # Send heartbeat — should flip back to ONLINE
            ws.send_json({"message_type": "HEARTBEAT"})
            ws.receive_json()  # HEARTBEAT_ACK
            assert container.presence_tracker.get(pid).status == PresenceStatus.ONLINE


# ---------------------------------------------------------------------------
# TestRealtimeSignalDelivery
# ---------------------------------------------------------------------------


class TestRealtimeSignalDelivery:
    def test_pending_signal_flushed_on_connect(self, server):
        """Signals emitted before WS connection are flushed immediately on connect."""
        anvil_id = _register(server, "Anvil")
        inspectra_id = _register(server, "Inspectra")

        # Emit signal to Anvil while it's offline (REST only)
        server.post(
            "/signals/emit",
            json={
                "type": "INFORM",
                "severity": "LOW",
                "source_product": inspectra_id,
                "target_product": anvil_id,
                "payload": {"msg": "pre-connect signal"},
                "metadata": {"broadcast": False},
            },
        )

        # Now Anvil connects — signal should be flushed in CONNECTED message
        with server.websocket_connect(f"/ws/products/{anvil_id}") as ws:
            connected_msg = ws.receive_json()
            assert connected_msg["pending_count"] == 1
            # Flushed immediately as a SIGNAL message
            signal_msg = ws.receive_json()
            assert signal_msg["message_type"] == "SIGNAL"
            assert signal_msg["signal"]["payload"]["msg"] == "pre-connect signal"

    def test_signal_delivered_realtime_while_connected(self, server):
        """Signal emitted while product is connected arrives immediately over WS."""
        anvil_id = _register(server, "Anvil")
        inspectra_id = _register(server, "Inspectra")

        received = []
        connected_event = threading.Event()

        def listener():
            with server.websocket_connect(f"/ws/products/{anvil_id}") as ws:
                msg = ws.receive_json()
                assert msg["message_type"] == "CONNECTED"
                connected_event.set()
                signal_msg = ws.receive_json()
                received.append(signal_msg)

        t = threading.Thread(target=listener, daemon=True)
        t.start()
        connected_event.wait(timeout=3)

        server.post(
            "/signals/emit",
            json={
                "type": "BLOCK",
                "severity": "CRITICAL",
                "source_product": inspectra_id,
                "target_product": anvil_id,
                "payload": {"reason": "SQL injection"},
                "metadata": {"broadcast": False},
            },
        )

        t.join(timeout=3)
        assert len(received) == 1
        assert received[0]["message_type"] == "SIGNAL"
        assert received[0]["signal"]["type"] == "BLOCK"

    def test_signal_not_in_rest_queue_after_ws_delivery(self, server):
        """Once delivered via WS (status=DELIVERED), signal no longer appears in REST pending."""
        anvil_id = _register(server, "Anvil")
        inspectra_id = _register(server, "Inspectra")

        with server.websocket_connect(f"/ws/products/{anvil_id}") as ws:
            ws.receive_json()  # CONNECTED

            server.post(
                "/signals/emit",
                json={
                    "type": "INFORM",
                    "severity": "LOW",
                    "source_product": inspectra_id,
                    "target_product": anvil_id,
                    "payload": {},
                    "metadata": {"broadcast": False},
                },
            )

            ws.receive_json()  # SIGNAL delivered

            # REST queue shows DELIVERED signals as absent from PENDING
            pending = server.get(f"/signals/pending/{anvil_id}").json()
            assert len(pending) == 0


# ---------------------------------------------------------------------------
# TestWebSocketAck
# ---------------------------------------------------------------------------


class TestWebSocketAck:
    def test_ws_ack_removes_from_pending(self, server):
        anvil_id = _register(server, "Anvil")
        inspectra_id = _register(server, "Inspectra")

        # Emit before connect so signal is PENDING
        resp = server.post(
            "/signals/emit",
            json={
                "type": "INTERRUPT",
                "severity": "HIGH",
                "source_product": inspectra_id,
                "target_product": anvil_id,
                "payload": {},
                "metadata": {"broadcast": False},
            },
        )
        signal_id = resp.json()["id"]

        with server.websocket_connect(f"/ws/products/{anvil_id}") as ws:
            ws.receive_json()  # CONNECTED
            signal_msg = ws.receive_json()  # flushed SIGNAL
            assert signal_msg["signal"]["id"] == signal_id

            # ACK via WebSocket
            ws.send_json({"message_type": "ACK", "signal_id": signal_id})

        # Signal should be gone from REST pending
        pending = server.get(f"/signals/pending/{anvil_id}").json()
        assert all(s["id"] != signal_id for s in pending)

    def test_ws_ack_invalid_signal_returns_error(self, server):
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()  # CONNECTED
            ws.send_json({"message_type": "ACK", "signal_id": "no-such-signal"})
            error_msg = ws.receive_json()
        assert error_msg["message_type"] == "ERROR"
        assert error_msg["code"] == "ack_error"


# ---------------------------------------------------------------------------
# TestBroadcastRealtime
# ---------------------------------------------------------------------------


class TestBroadcastRealtime:
    def test_broadcast_reaches_all_connected(self, server):
        """A LEARN broadcast reaches every connected product except the source."""
        anvil_id = _register(server, "Anvil")
        inspectra_id = _register(server, "Inspectra")
        graph_id = _register(server, "GraphEngine")

        anvil_received = []
        graph_received = []
        anvil_ready = threading.Event()
        graph_ready = threading.Event()

        def anvil_listener():
            with server.websocket_connect(f"/ws/products/{anvil_id}") as ws:
                ws.receive_json()  # CONNECTED
                anvil_ready.set()
                # May receive PRESENCE_UPDATE messages before the SIGNAL
                while True:
                    msg = ws.receive_json()
                    if msg["message_type"] == "SIGNAL":
                        anvil_received.append(msg)
                        break

        def graph_listener():
            with server.websocket_connect(f"/ws/products/{graph_id}") as ws:
                ws.receive_json()  # CONNECTED
                graph_ready.set()
                while True:
                    msg = ws.receive_json()
                    if msg["message_type"] == "SIGNAL":
                        graph_received.append(msg)
                        break

        t1 = threading.Thread(target=anvil_listener, daemon=True)
        t2 = threading.Thread(target=graph_listener, daemon=True)
        t1.start()
        t2.start()
        anvil_ready.wait(timeout=3)
        graph_ready.wait(timeout=3)

        # Inspectra emits a LEARN broadcast (not connected via WS)
        server.post(
            "/signals/emit",
            json={
                "type": "LEARN",
                "severity": "LOW",
                "source_product": inspectra_id,
                "payload": {"pattern": "hardcoded_secret"},
                "metadata": {"broadcast": True},
            },
        )

        t1.join(timeout=3)
        t2.join(timeout=3)

        assert len(anvil_received) == 1
        assert anvil_received[0]["signal"]["type"] == "LEARN"
        assert len(graph_received) == 1

    def test_broadcast_presence_update_on_connect(self, server):
        """When Inspectra connects, Anvil receives a PRESENCE_UPDATE."""
        anvil_id = _register(server, "Anvil")
        inspectra_id = _register(server, "Inspectra")

        anvil_ready = threading.Event()
        presence_msgs = []

        def anvil_listener():
            with server.websocket_connect(f"/ws/products/{anvil_id}") as ws:
                ws.receive_json()  # CONNECTED for Anvil
                anvil_ready.set()
                msg = ws.receive_json()  # should be PRESENCE_UPDATE for Inspectra
                presence_msgs.append(msg)

        t = threading.Thread(target=anvil_listener, daemon=True)
        t.start()
        anvil_ready.wait(timeout=3)

        # Now Inspectra connects
        with server.websocket_connect(f"/ws/products/{inspectra_id}") as ws:
            ws.receive_json()  # CONNECTED for Inspectra

        t.join(timeout=3)
        assert len(presence_msgs) == 1
        assert presence_msgs[0]["message_type"] == "PRESENCE_UPDATE"
        assert presence_msgs[0]["product_name"] == "Inspectra"
        assert presence_msgs[0]["status"] == "ONLINE"


# ---------------------------------------------------------------------------
# TestOfflineQueueFallback
# ---------------------------------------------------------------------------


class TestOfflineQueueFallback:
    def test_offline_signal_queued_in_rest(self, server):
        """Signal to an offline product stays in the REST pending queue."""
        anvil_id = _register(server, "Anvil")
        inspectra_id = _register(server, "Inspectra")

        server.post(
            "/signals/emit",
            json={
                "type": "BLOCK",
                "severity": "CRITICAL",
                "source_product": inspectra_id,
                "target_product": anvil_id,
                "payload": {"reason": "test"},
                "metadata": {"broadcast": False},
            },
        )

        # Anvil never connected via WS — signal should be in REST queue
        pending = server.get(f"/signals/pending/{anvil_id}").json()
        assert len(pending) == 1
        assert pending[0]["type"] == "BLOCK"

    def test_polling_and_realtime_coexist(self, server):
        """REST polling still works when WebSocket is also available."""
        anvil_id = _register(server, "Anvil")
        inspectra_id = _register(server, "Inspectra")

        # Emit a signal while offline
        server.post(
            "/signals/emit",
            json={
                "type": "INFORM",
                "severity": "LOW",
                "source_product": inspectra_id,
                "target_product": anvil_id,
                "payload": {"step": 1},
                "metadata": {"broadcast": False},
            },
        )

        # Connect via WS — signal is flushed (DELIVERED)
        with server.websocket_connect(f"/ws/products/{anvil_id}") as ws:
            ws.receive_json()  # CONNECTED (pending_count=1)
            ws.receive_json()  # SIGNAL (flushed)

            # REST pending is now empty (DELIVERED means it won't appear again)
            pending = server.get(f"/signals/pending/{anvil_id}").json()
            assert len(pending) == 0


# ---------------------------------------------------------------------------
# TestPresenceEndpoints
# ---------------------------------------------------------------------------


class TestPresenceEndpoints:
    def test_list_presence_empty_before_ws(self, server):
        _register(server, "Anvil")
        data = server.get("/presence").json()
        assert data == []

    def test_list_presence_after_connect(self, server):
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()
            data = server.get("/presence").json()
        assert len(data) == 1
        assert data[0]["product_name"] == "Anvil"

    def test_get_presence_not_found(self, server):
        resp = server.get("/presence/no-such-product")
        assert resp.status_code == 404

    def test_get_presence_fields(self, server):
        pid = _register(server, "Anvil")
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()
            data = server.get(f"/presence/{pid}").json()
        assert "product_id" in data
        assert "product_name" in data
        assert "status" in data
        assert "connected" in data
        assert "last_seen" in data

    def test_reconnect_presence_resets(self, server):
        pid = _register(server, "Anvil")
        # First connection
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()
        assert server.get(f"/presence/{pid}").json()["status"] == "OFFLINE"

        # Second connection
        with server.websocket_connect(f"/ws/products/{pid}") as ws:
            ws.receive_json()
            assert server.get(f"/presence/{pid}").json()["status"] == "ONLINE"
        assert server.get(f"/presence/{pid}").json()["status"] == "OFFLINE"
