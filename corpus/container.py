"""
Corpus dependency-injection container.

Created once per server lifespan. All services are wired here so that routes,
the SDK, and WebSocket handlers all consume the same service instances without
importing concrete infrastructure classes.
"""

import aiosqlite

from corpus.audit.audit_log import AuditLog
from corpus.clearance.clearance_engine import ClearanceEngine
from corpus.events.event_bus import EventBus
from corpus.events.hooks import register_logging_hooks, register_state_hooks
from corpus.gravity.gravity_engine import GravityEngine
from corpus.gravity.signal_prioritizer import SignalPrioritizer
from corpus.interrupts.interrupt_bridge import InterruptBridge
from corpus.interrupts.interrupt_rules import InterruptRules
from corpus.memory.episode_store import EpisodeStore
from corpus.memory.learning_artifacts import LearningArtifacts
from corpus.memory.memory_service import MemoryService
from corpus.policy.policy_engine import PolicyEngine
from corpus.policy.policy_loader import PolicyLoader
from corpus.registry.product_registry import ProductRegistry
from corpus.runtime.state import RuntimeState
from corpus.services.checkpoint_service import CheckpointService
from corpus.services.delivery_service import DeliveryService
from corpus.services.product_service import ProductService
from corpus.services.runtime_service import RuntimeService
from corpus.services.signal_service import SignalService
from corpus.signal_engine.router import SignalRouter
from corpus.storage.checkpoint_repository import CheckpointRepository, DecisionRepository
from corpus.storage.repositories import DeliveryRepository, SignalRepository
from corpus.guardian.guardian_engine import GuardianEngine
from corpus.guardian.guardian_models import GuardianMode
from corpus.guardian.guardian_state import GuardianState
from corpus.observability.dashboard_service import DashboardService
from corpus.orchestration.coordination_plan import CoordinationPlan
from corpus.orchestration.orchestration_state import OrchestrationState
from corpus.orchestration.product_graph import ProductGraph
from corpus.orchestration.response_collector import ResponseCollector
from corpus.orchestration.synthesis_engine import SynthesisEngine
from corpus.orchestration.workflow_engine import WorkflowEngine
from corpus.translation.translation_engine import TranslationEngine
from corpus.translation.translator import Translator
from corpus.websocket.connection_manager import ConnectionManager
from corpus.websocket.heartbeat_monitor import HeartbeatMonitor
from corpus.websocket.presence_tracker import PresenceTracker
from corpus.websocket.realtime_dispatcher import RealtimeDispatcher
from corpus.websocket.websocket_service import WebSocketService


class CorpusContainer:
    """
    Wires all Corpus components for a single server instance.

    Dependency graph:
        aiosqlite.Connection
            → Repositories (ProductRepository, SignalRepository, DeliveryRepository)
            → Domain services (ProductRegistry, SignalRouter)
            → Application services (ProductService, SignalService, DeliveryService, RuntimeService)
        EventBus
            → hooks: logging + runtime-state counters
        WebSocket layer
            → ConnectionManager, PresenceTracker, HeartbeatMonitor
            → RealtimeDispatcher → WebSocketService
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        # Infrastructure
        self._conn = conn
        self._signal_repo = SignalRepository(conn)
        self._delivery_repo = DeliveryRepository(conn)

        # Event bus (wired before everything so services can subscribe)
        self.event_bus = EventBus()

        # Domain layer
        self._registry = ProductRegistry(conn)
        self._router = SignalRouter(conn, self._registry)

        # Runtime state (in-memory session counters)
        self._runtime_state = RuntimeState()

        # Application services (the public service boundary)
        self.product_service = ProductService(self._registry, self.event_bus)
        self.signal_service = SignalService(self._router, self.event_bus)
        self.delivery_service = DeliveryService(self._signal_repo, self._delivery_repo)
        self.runtime_service = RuntimeService(
            self._runtime_state, self._registry, self._router
        )

        # WebSocket / realtime layer
        self.connection_manager = ConnectionManager()
        self.presence_tracker = PresenceTracker()
        self.heartbeat_monitor = HeartbeatMonitor(
            presence_tracker=self.presence_tracker,
            connection_manager=self.connection_manager,
            event_bus=self.event_bus,
        )
        self.realtime_dispatcher = RealtimeDispatcher(
            connection_manager=self.connection_manager,
            signal_repo=self._signal_repo,
            delivery_repo=self._delivery_repo,
            event_bus=self.event_bus,
        )
        self.websocket_service = WebSocketService(
            connection_manager=self.connection_manager,
            presence_tracker=self.presence_tracker,
            dispatcher=self.realtime_dispatcher,
            heartbeat_monitor=self.heartbeat_monitor,
            signal_repo=self._signal_repo,
            delivery_repo=self._delivery_repo,
            event_bus=self.event_bus,
        )

        # Phase 4 — checkpoint governance layer
        self._audit = AuditLog(conn)
        self._checkpoint_repo = CheckpointRepository(conn)
        self._decision_repo = DecisionRepository(conn)
        self._interrupt_rules = InterruptRules()
        self._clearance_engine = ClearanceEngine(self._signal_repo, self._interrupt_rules)
        self.checkpoint_service = CheckpointService(
            checkpoint_repo=self._checkpoint_repo,
            decision_repo=self._decision_repo,
            clearance_engine=self._clearance_engine,
            registry=self._registry,
            audit=self._audit,
            event_bus=self.event_bus,
            connection_manager=self.connection_manager,
        )
        self._interrupt_bridge = InterruptBridge(self.event_bus, self._interrupt_rules)
        self._interrupt_bridge.set_checkpoint_service(lambda: self.checkpoint_service)

        # Phase 5 — Signal Gravity Engine
        self.gravity_engine = GravityEngine(event_bus=self.event_bus)
        self.signal_prioritizer = SignalPrioritizer(engine=self.gravity_engine)

        # Phase 6 — AI Translation Engine
        self.translator = Translator(
            engine=TranslationEngine(),
            event_bus=self.event_bus,
        )

        # Phase 7 — Episodic Memory & Learning
        self._episode_store = EpisodeStore(conn)
        self.memory_service = MemoryService(
            store=self._episode_store,
            event_bus=self.event_bus,
            artifacts=LearningArtifacts(),
        )

        # Phase 8 — Policy & Governance Engine
        _loader = PolicyLoader()
        _mode, _trust, _rules = _loader.default()
        self.policy_engine = PolicyEngine(
            mode=_mode,
            trust_registry=_trust,
            rules=_rules,
            event_bus=self.event_bus,
        )

        # Phase 9 — Multi-Product Orchestration
        self.product_graph = ProductGraph()
        self._orchestration_state = OrchestrationState(conn)
        self.workflow_engine = WorkflowEngine(
            state=self._orchestration_state,
            graph=self.product_graph,
            synthesis_engine=SynthesisEngine(),
            response_collector=ResponseCollector(),
            task_router=None,  # wired lazily to avoid circular dep with signal_service
            event_bus=self.event_bus,
            policy_engine=self.policy_engine,
            gravity_engine=self.gravity_engine,
            memory_service=self.memory_service,
        )

        # Phase 10 — Guardian Mode
        self._guardian_state = GuardianState(conn)
        self.guardian_engine = GuardianEngine(
            state=self._guardian_state,
            event_bus=self.event_bus,
            mode=GuardianMode.GUARDIAN,
            policy_engine=self.policy_engine,
            memory_service=self.memory_service,
            gravity_engine=self.gravity_engine,
        )

        # Phase 11 — Observability Dashboard
        self.dashboard_service = DashboardService(self)

        # Wire hooks (after all services exist so state hooks can reference them)
        register_logging_hooks(self.event_bus)
        register_state_hooks(self.event_bus, self._runtime_state)
