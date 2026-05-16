"""corpus-sdk-python — the official SDK for integrating products with Corpus."""

from corpus_sdk.checkpoint_client import CheckpointClient
from corpus_sdk.checkpoint_models import CheckpointInfo, DecisionInfo
from corpus_sdk.client import CorpusClient
from corpus_sdk.config import CorpusConfig
from corpus_sdk.gravity_client import GravityClient, GravityResult
from corpus_sdk.memory_client import MemoryClient
from corpus_sdk.policy_client import PolicyClient, PolicyEvalResult
from corpus_sdk.realtime_client import CorpusRealtimeClient
from corpus_sdk.translation_client import TranslationClient
from corpus_sdk.translation_client import TranslationResult as SDKTranslationResult
from corpus_sdk.exceptions import (
    CorpusAPIError,
    CorpusConnectionError,
    CorpusSDKError,
    NotConnectedError,
    ProductAlreadyRegisteredError,
    ProductNotFoundError,
    SignalAcknowledgementError,
    SignalExpiredError,
    SignalNotFoundError,
    SignalRoutingError,
)
from corpus_sdk.models import EmittedSignal, HealthInfo, ProductInfo, ReceivedSignal
from corpus_sdk.transport import HTTPTransport, InProcessTransport

__version__ = "0.1.0"

__all__ = [
    # Main client
    "CorpusClient",
    "CorpusConfig",
    "CorpusRealtimeClient",
    # Checkpoint governance
    "CheckpointClient",
    "CheckpointInfo",
    "DecisionInfo",
    # Intelligence
    "GravityClient",
    "GravityResult",
    "TranslationClient",
    "SDKTranslationResult",
    "MemoryClient",
    "PolicyClient",
    "PolicyEvalResult",
    # Models
    "ProductInfo",
    "ReceivedSignal",
    "EmittedSignal",
    "HealthInfo",
    # Transport
    "HTTPTransport",
    "InProcessTransport",
    # Exceptions
    "CorpusSDKError",
    "CorpusAPIError",
    "CorpusConnectionError",
    "NotConnectedError",
    "ProductAlreadyRegisteredError",
    "ProductNotFoundError",
    "SignalNotFoundError",
    "SignalExpiredError",
    "SignalRoutingError",
    "SignalAcknowledgementError",
]
