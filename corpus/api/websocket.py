"""WebSocket endpoint — products connect here for real-time signal delivery."""

from __future__ import annotations

import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from corpus.dependencies import get_container

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/products/{product_id}")
async def websocket_endpoint(websocket: WebSocket, product_id: str) -> None:
    """
    Real-time signal channel for a registered product.

    Flow:
      1. Product upgrades to WebSocket
      2. Corpus validates product is registered
      3. CONNECTED message sent with pending signal count
      4. Any queued signals are flushed immediately
      5. Product can send ACK and HEARTBEAT messages
      6. On disconnect, product is marked OFFLINE
    """
    container = websocket.app.state.container
    ws_service = container.websocket_service
    product_service = container.product_service
    signal_service = container.signal_service

    # Validate product registration before accepting the connection
    try:
        product = await product_service.get(product_id)
    except Exception:
        await websocket.close(code=4004, reason="Product not registered")
        return

    await websocket.accept()

    try:
        await ws_service.handle_connect(
            product_id=product.product_id,
            product_name=product.name,
            websocket=websocket,
            signal_service=signal_service,
        )
        while True:
            data = await websocket.receive_json()
            await ws_service.handle_message(
                product_id=product.product_id,
                product_name=product.name,
                data=data,
                signal_service=signal_service,
            )
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # Shield from external cancel scopes (e.g. test teardown) so presence
        # state is always updated before the task exits.
        with anyio.CancelScope(shield=True):
            await ws_service.handle_disconnect(
                product_id=product.product_id,
                product_name=product.name,
            )
