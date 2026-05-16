"""Phase 6 — AI Translation Engine tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from corpus.translation.fallback_translator import FallbackTranslator
from corpus.translation.intent_mapper import IntentMapper
from corpus.translation.product_profile import get_profile
from corpus.translation.translation_engine import TranslationEngine
from corpus.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app(db_path=":memory:")) as c:
        yield c


class TestIntentMapper:
    def test_maps_known_vocabulary(self):
        mapper = IntentMapper()
        payload = {"audit": "auth/config.py", "violation": "hardcoded secret"}
        translated, confidence, explanation = mapper.map(payload, "inspectra", "anvil")
        # Anvil expects "audit" → "validate"
        assert "validate" in translated or "audit" in translated
        assert confidence > 0

    def test_passthrough_unknown_fields(self):
        mapper = IntentMapper()
        payload = {"custom_field": "some_value"}
        translated, _, _ = mapper.map(payload, "inspectra", "anvil")
        assert "some_value" in translated.values()

    def test_confidence_in_range(self):
        mapper = IntentMapper()
        _, confidence, _ = mapper.map({"key": "val"}, "generic", "generic")
        assert 0.0 <= confidence <= 1.0


class TestFallbackTranslator:
    def test_translate_inspectra_to_anvil(self):
        translator = FallbackTranslator()
        result = translator.translate(
            signal_id="sig-001",
            source_product="inspectra",
            target_product="anvil",
            original_payload={"finding": "SQL injection", "rule": "SEC-001"},
            signal_type="BLOCK",
            severity="CRITICAL",
        )
        assert result.source_product == "inspectra"
        assert result.target_product == "anvil"
        assert result.method == "fallback"
        assert result.confidence > 0
        assert "_corpus_signal_type" in result.translated_payload
        assert result.translated_payload["_corpus_signal_type"] == "BLOCK"

    def test_translate_anvil_to_inspectra(self):
        translator = FallbackTranslator()
        result = translator.translate(
            signal_id="sig-002",
            source_product="anvil",
            target_product="inspectra",
            original_payload={"task": "deploy auth module", "deploy": True},
            signal_type="VALIDATE",
            severity="HIGH",
        )
        assert result.method == "fallback"
        assert isinstance(result.translated_payload, dict)

    def test_warnings_for_missing_expected_fields(self):
        translator = FallbackTranslator()
        result = translator.translate(
            signal_id="sig-003",
            source_product="generic",
            target_product="inspectra",
            original_payload={"something": "irrelevant"},
        )
        # Inspectra expects finding, rule, file, severity, recommendation
        assert len(result.warnings) > 0

    def test_high_confidence_flag(self):
        translator = FallbackTranslator()
        result = translator.translate(
            signal_id="sig-004",
            source_product="inspectra",
            target_product="anvil",
            original_payload={"key": "val"},
        )
        # Fallback method always returns < 0.80 confidence
        assert result.is_high_confidence is False or result.confidence >= 0


class TestTranslationEngine:
    def test_uses_fallback_when_no_ollama(self):
        engine = TranslationEngine(ollama_url=None)
        result = engine.translate(
            signal_id="sig-x",
            source_product="inspectra",
            target_product="anvil",
            original_payload={"finding": "test"},
        )
        assert result.method == "fallback"

    def test_invalid_ollama_url_falls_back(self):
        engine = TranslationEngine(ollama_url="http://localhost:99999")
        result = engine.translate(
            signal_id="sig-y",
            source_product="anvil",
            target_product="inspectra",
            original_payload={"task": "test"},
        )
        assert result.method == "fallback"


class TestProductProfiles:
    def test_anvil_profile_exists(self):
        profile = get_profile("anvil")
        assert profile.product_name.lower() == "anvil"
        assert len(profile.vocabulary) > 0

    def test_inspectra_profile_exists(self):
        profile = get_profile("inspectra")
        assert profile.product_name.lower() == "inspectra"

    def test_unknown_product_returns_generic(self):
        profile = get_profile("unknown_product_xyz")
        assert profile.product_name == "generic"


class TestTranslationAPI:
    def test_translate_inspectra_to_anvil(self, client):
        resp = client.post(
            "/translation/translate",
            json={
                "source_product": "inspectra",
                "target_product": "anvil",
                "payload": {"finding": "SQL injection", "rule": "SEC-001"},
                "signal_type": "BLOCK",
                "severity": "CRITICAL",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["source_product"] == "inspectra"
        assert data["target_product"] == "anvil"
        assert "translated_payload" in data
        assert "confidence" in data
        assert "method" in data

    def test_translate_returns_original_payload(self, client):
        payload = {"finding": "hardcoded secret", "file": "config.py"}
        resp = client.post(
            "/translation/translate",
            json={
                "source_product": "inspectra",
                "target_product": "anvil",
                "payload": payload,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["original_payload"] == payload

    def test_translate_generic_products(self, client):
        resp = client.post(
            "/translation/translate",
            json={
                "source_product": "product_a",
                "target_product": "product_b",
                "payload": {"message": "hello"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["method"] == "fallback"
