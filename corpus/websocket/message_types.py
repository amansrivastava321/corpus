"""Structured WebSocket message types for the Corpus real-time bus."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WsMessageType(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    SIGNAL = "SIGNAL"
    ACK = "ACK"
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"
    PRESENCE_UPDATE = "PRESENCE_UPDATE"
    PENDING_FLUSH = "PENDING_FLUSH"
    ERROR = "ERROR"
    # Phase 4 — checkpoint governance
    CHECKPOINT_REGISTERED = "CHECKPOINT_REGISTERED"
    CLEARANCE_DECISION = "CLEARANCE_DECISION"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
    EXECUTION_RESUMED = "EXECUTION_RESUMED"
    EXECUTION_ESCALATED = "EXECUTION_ESCALATED"


class WsMessage(BaseModel):
    message_type: WsMessageType


class ConnectedMessage(WsMessage):
    message_type: WsMessageType = WsMessageType.CONNECTED
    product_id: str
    product_name: str
    pending_count: int = 0


class DisconnectedMessage(WsMessage):
    message_type: WsMessageType = WsMessageType.DISCONNECTED
    product_id: str


class SignalMessage(WsMessage):
    message_type: WsMessageType = WsMessageType.SIGNAL
    signal: dict[str, Any]


class AckMessage(WsMessage):
    message_type: WsMessageType = WsMessageType.ACK
    signal_id: str


class HeartbeatMessage(WsMessage):
    message_type: WsMessageType = WsMessageType.HEARTBEAT


class HeartbeatAckMessage(WsMessage):
    message_type: WsMessageType = WsMessageType.HEARTBEAT_ACK
    server_time: str = Field(default="")


class PresenceUpdateMessage(WsMessage):
    message_type: WsMessageType = WsMessageType.PRESENCE_UPDATE
    product_id: str
    product_name: str
    status: str


class PendingFlushMessage(WsMessage):
    message_type: WsMessageType = WsMessageType.PENDING_FLUSH
    count: int


class ErrorMessage(WsMessage):
    message_type: WsMessageType = WsMessageType.ERROR
    code: str
    detail: str


def parse_client_message(data: dict[str, Any]) -> WsMessage:
    """Parse an incoming client message dict into a typed WsMessage."""
    msg_type = data.get("message_type", "")
    if msg_type == WsMessageType.ACK:
        return AckMessage.model_validate(data)
    if msg_type == WsMessageType.HEARTBEAT:
        return HeartbeatMessage.model_validate(data)
    return WsMessage(message_type=WsMessageType.ERROR)
