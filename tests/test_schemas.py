"""Phase 0 schema tests — validates all Pydantic models and the SchemaValidator."""

import pytest
from pydantic import ValidationError

from corpus.schemas.checkpoint import Checkpoint, CheckpointStatus, CheckpointType
from corpus.schemas.decision import ClearanceDecision, DecisionType
from corpus.schemas.episode import Episode, EpisodeEvent, EpisodeEventType, EpisodeStatus
from corpus.schemas.product import ProductCapability, ProductRegistration, ProductStatus
from corpus.schemas.signal import Signal, SignalSeverity, SignalStatus, SignalType
from corpus.schemas.validator import SchemaValidationError, SchemaValidator


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


class TestSignal:
    def test_create_minimal_signal(self):
        sig = Signal(type=SignalType.INFORM, severity=SignalSeverity.LOW, source_product="anvil")
        assert sig.id is not None
        assert sig.status == SignalStatus.PENDING
        assert sig.timestamp is not None
        assert sig.payload == {}

    def test_gravity_weight_critical_block(self):
        sig = Signal(
            type=SignalType.BLOCK, severity=SignalSeverity.CRITICAL, source_product="inspectra"
        )
        assert sig.gravity_weight() == 30.0  # 10.0 × 3.0

    def test_gravity_weight_low_inform(self):
        sig = Signal(
            type=SignalType.INFORM, severity=SignalSeverity.LOW, source_product="anvil"
        )
        assert sig.gravity_weight() == 0.5  # 1.0 × 0.5

    def test_requires_interrupt_for_interrupt_type(self):
        sig = Signal(
            type=SignalType.INTERRUPT, severity=SignalSeverity.HIGH, source_product="inspectra"
        )
        assert sig.requires_interrupt() is True

    def test_requires_interrupt_for_block_type(self):
        sig = Signal(
            type=SignalType.BLOCK, severity=SignalSeverity.CRITICAL, source_product="inspectra"
        )
        assert sig.requires_interrupt() is True

    def test_requires_interrupt_false_for_inform(self):
        sig = Signal(
            type=SignalType.INFORM, severity=SignalSeverity.LOW, source_product="anvil"
        )
        assert sig.requires_interrupt() is False

    def test_broadcast_signal_has_no_target(self):
        from corpus.schemas.signal import SignalMetadata

        sig = Signal(
            type=SignalType.LEARN,
            severity=SignalSeverity.LOW,
            source_product="inspectra",
            target_product=None,
            metadata=SignalMetadata(broadcast=True),
        )
        assert sig.target_product is None

    def test_broadcast_with_target_raises(self):
        from corpus.schemas.signal import SignalMetadata

        with pytest.raises(ValidationError, match="broadcast"):
            Signal(
                type=SignalType.INFORM,
                severity=SignalSeverity.LOW,
                source_product="anvil",
                target_product="inspectra",
                metadata=SignalMetadata(broadcast=True),
            )

    def test_empty_source_product_raises(self):
        with pytest.raises(ValidationError):
            Signal(type=SignalType.INFORM, severity=SignalSeverity.LOW, source_product="   ")

    def test_ttl_expiry(self):
        from datetime import datetime, timedelta, timezone

        sig = Signal(
            type=SignalType.INFORM,
            severity=SignalSeverity.LOW,
            source_product="anvil",
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=400),
            ttl=300,
        )
        assert sig.is_expired() is True

    def test_no_ttl_never_expires(self):
        sig = Signal(type=SignalType.INFORM, severity=SignalSeverity.LOW, source_product="anvil")
        assert sig.is_expired() is False

    def test_correlation_and_parent_ids(self):
        sig = Signal(
            type=SignalType.INTERRUPT,
            severity=SignalSeverity.HIGH,
            source_product="inspectra",
            correlation_id="corr-001",
            parent_signal_id="parent-001",
        )
        assert sig.correlation_id == "corr-001"
        assert sig.parent_signal_id == "parent-001"


# ---------------------------------------------------------------------------
# ProductRegistration
# ---------------------------------------------------------------------------


class TestProductRegistration:
    def test_create_minimal_product(self):
        p = ProductRegistration(name="Anvil", version="1.0.0")
        assert p.product_id is not None
        assert p.heartbeat_interval == 30
        assert p.status == ProductStatus.ACTIVE

    def test_capabilities(self):
        p = ProductRegistration(
            name="Inspectra",
            version="1.2.0",
            capabilities=[ProductCapability.AUDIT, ProductCapability.INTERRUPT],
        )
        assert p.has_capability(ProductCapability.AUDIT) is True
        assert p.has_capability(ProductCapability.ORCHESTRATE) is False

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            ProductRegistration(name="", version="1.0.0")

    def test_is_stale_when_never_seen(self):
        p = ProductRegistration(name="Ghost", version="0.1.0")
        assert p.is_stale() is True

    def test_mark_seen(self):
        p = ProductRegistration(name="Anvil", version="1.0.0")
        p.mark_seen()
        assert p.last_seen is not None
        assert p.is_stale() is False


# ---------------------------------------------------------------------------
# Episode
# ---------------------------------------------------------------------------


class TestEpisode:
    def test_create_minimal_episode(self):
        ep = Episode(title="Auth vulnerability detected")
        assert ep.episode_id is not None
        assert ep.status == EpisodeStatus.ACTIVE
        assert ep.events == []

    def test_add_event_tracks_signal_and_product(self):
        ep = Episode(title="Test episode")
        event = EpisodeEvent(
            event_type=EpisodeEventType.SIGNAL_RECEIVED,
            signal_id="sig-123",
            product_id="anvil",
        )
        ep.add_event(event)
        assert "sig-123" in ep.signal_ids
        assert "anvil" in ep.products_involved
        assert len(ep.events) == 1

    def test_add_event_deduplicates_ids(self):
        ep = Episode(title="Dedup test")
        for _ in range(3):
            ep.add_event(
                EpisodeEvent(
                    event_type=EpisodeEventType.SIGNAL_RECEIVED,
                    signal_id="sig-abc",
                    product_id="anvil",
                )
            )
        assert ep.signal_ids.count("sig-abc") == 1
        assert ep.products_involved.count("anvil") == 1

    def test_resolve_episode(self):
        ep = Episode(title="Resolved episode")
        ep.resolve("Vulnerability patched")
        assert ep.status == EpisodeStatus.RESOLVED
        assert ep.resolved_at is not None
        assert ep.outcome == "Vulnerability patched"

    def test_duration_before_resolve_is_none(self):
        ep = Episode(title="Ongoing")
        assert ep.duration_seconds() is None

    def test_duration_after_resolve(self):
        ep = Episode(title="Finished")
        ep.resolve("done")
        assert ep.duration_seconds() is not None
        assert ep.duration_seconds() >= 0


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------


class TestCheckpoint:
    def test_create_checkpoint(self):
        cp = Checkpoint(checkpoint_type=CheckpointType.PRE_COMMIT, product_id="anvil")
        assert cp.checkpoint_id is not None
        assert cp.status == CheckpointStatus.PENDING

    def test_is_terminal_cleared(self):
        cp = Checkpoint(
            checkpoint_type=CheckpointType.PRE_COMMIT,
            product_id="anvil",
            status=CheckpointStatus.CLEARED,
        )
        assert cp.is_terminal() is True

    def test_is_terminal_blocked(self):
        cp = Checkpoint(
            checkpoint_type=CheckpointType.PRE_RELEASE,
            product_id="anvil",
            status=CheckpointStatus.BLOCKED,
        )
        assert cp.is_terminal() is True

    def test_pending_is_not_terminal(self):
        cp = Checkpoint(checkpoint_type=CheckpointType.PRE_COMMIT, product_id="anvil")
        assert cp.is_terminal() is False

    def test_no_expires_at_never_expired(self):
        cp = Checkpoint(checkpoint_type=CheckpointType.PRE_EXECUTION, product_id="anvil")
        assert cp.is_expired() is False


# ---------------------------------------------------------------------------
# ClearanceDecision
# ---------------------------------------------------------------------------


class TestClearanceDecision:
    def test_allow_decision_allows_continuation(self):
        d = ClearanceDecision(
            checkpoint_id="cp-001", decision=DecisionType.ALLOW, reason="No risk found"
        )
        assert d.allows_continuation() is True
        assert d.is_blocking() is False
        assert d.requires_action() is False

    def test_warn_decision_allows_continuation(self):
        d = ClearanceDecision(
            checkpoint_id="cp-001", decision=DecisionType.WARN, reason="Minor smell detected"
        )
        assert d.allows_continuation() is True

    def test_block_decision_is_blocking(self):
        d = ClearanceDecision(
            checkpoint_id="cp-002",
            decision=DecisionType.BLOCK,
            reason="Critical vulnerability",
        )
        assert d.is_blocking() is True
        assert d.allows_continuation() is False
        assert d.requires_action() is True

    def test_escalate_decision_is_blocking(self):
        d = ClearanceDecision(
            checkpoint_id="cp-003",
            decision=DecisionType.ESCALATE,
            reason="Unresolved after timeout",
        )
        assert d.is_blocking() is True

    def test_delay_requires_action(self):
        d = ClearanceDecision(
            checkpoint_id="cp-004",
            decision=DecisionType.DELAY,
            reason="Awaiting Inspectra audit",
            delay_seconds=60,
        )
        assert d.requires_action() is True
        assert d.delay_seconds == 60

    def test_empty_reason_raises(self):
        with pytest.raises(ValidationError):
            ClearanceDecision(checkpoint_id="cp-005", decision=DecisionType.ALLOW, reason="  ")


# ---------------------------------------------------------------------------
# SchemaValidator
# ---------------------------------------------------------------------------


class TestSchemaValidator:
    def test_validate_valid_signal(self):
        result = SchemaValidator.validate(
            "Signal", {"type": "INFORM", "severity": "LOW", "source_product": "anvil"}
        )
        assert isinstance(result, Signal)

    def test_validate_unknown_schema_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown schema"):
            SchemaValidator.validate("Bogus", {})

    def test_validate_invalid_data_raises_schema_error(self):
        with pytest.raises(SchemaValidationError):
            SchemaValidator.validate("Signal", {"type": "NOT_A_TYPE"})

    def test_is_valid_true(self):
        assert SchemaValidator.is_valid(
            "Signal", {"type": "BLOCK", "severity": "CRITICAL", "source_product": "inspectra"}
        )

    def test_is_valid_false(self):
        assert not SchemaValidator.is_valid("Signal", {"type": "BOGUS"})

    def test_available_schemas_contains_all_types(self):
        schemas = SchemaValidator.available_schemas()
        expected = {
            "Signal",
            "ProductRegistration",
            "ProductHeartbeat",
            "Episode",
            "EpisodeEvent",
            "Checkpoint",
            "ClearanceDecision",
        }
        assert expected.issubset(set(schemas))
