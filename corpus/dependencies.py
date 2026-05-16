"""FastAPI dependency functions — extract services from the container on app.state."""

from fastapi import Request

from corpus.container import CorpusContainer
from corpus.services.checkpoint_service import CheckpointService
from corpus.services.product_service import ProductService
from corpus.services.runtime_service import RuntimeService
from corpus.services.signal_service import SignalService
from corpus.websocket.websocket_service import WebSocketService


def get_container(request: Request) -> CorpusContainer:
    return request.app.state.container


def get_product_service(request: Request) -> ProductService:
    return request.app.state.container.product_service


def get_signal_service(request: Request) -> SignalService:
    return request.app.state.container.signal_service


def get_runtime_service(request: Request) -> RuntimeService:
    return request.app.state.container.runtime_service


def get_ws_service(request: Request) -> WebSocketService:
    return request.app.state.container.websocket_service


def get_checkpoint_service(request: Request) -> CheckpointService:
    return request.app.state.container.checkpoint_service
