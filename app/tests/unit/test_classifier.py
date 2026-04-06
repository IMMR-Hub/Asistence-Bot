from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.intent_classifier.classifier import IntentClassifier
from app.schemas.common import ClassificationResult, NormalizedMessage
from app.schemas.tenant import TenantConfigSchema

import uuid
from datetime import datetime, timezone


def _make_message(text: str, tenant_id: uuid.UUID | None = None) -> NormalizedMessage:
    return NormalizedMessage(
        message_id="test-001",
        tenant_id=tenant_id or uuid.uuid4(),
        channel="whatsapp",
        direction="inbound",
        contact_phone="595981000000",
        text_content=text,
        received_at=datetime.now(timezone.utc),
    )


def _make_config(overrides: dict | None = None) -> TenantConfigSchema:
    base = {
        "tenant_slug": "test",
        "business_name": "Test",
        "classification_overrides": overrides or {
            "hot_keywords": ["precio", "comprar"],
            "human_request_keywords": ["asesor", "humano"],
        },
    }
    return TenantConfigSchema.model_validate(base)


MOCK_CLASSIFICATION_RESPONSE = json.dumps({
    "intent": "pricing_request",
    "lead_temperature": "warm",
    "urgency": "medium",
    "confidence": 0.88,
    "summary": "Customer asking about prices",
    "entities": {
        "customer_name": None,
        "product_or_service_interest": "madera",
        "budget_hint": None,
        "location_hint": None,
        "preferred_contact_time": None,
        "language": "es",
    },
})


@pytest.mark.asyncio
async def test_classify_valid_output():
    classifier = IntentClassifier()
    msg = _make_message("¿Cuánto cuesta la madera?")
    config = _make_config()

    with patch.object(classifier.client, "generate", new=AsyncMock(return_value=MOCK_CLASSIFICATION_RESPONSE)):
        result = await classifier.classify(msg, config)

    assert result.intent == "pricing_request"
    assert result.lead_temperature == "warm"
    assert result.confidence == 0.88
    assert result.entities.get("product_or_service_interest") == "madera"


@pytest.mark.asyncio
async def test_hot_keyword_override():
    classifier = IntentClassifier()
    msg = _make_message("Quiero comprar hoy mismo")
    config = _make_config()

    cold_response = json.dumps({
        "intent": "product_inquiry",
        "lead_temperature": "cold",
        "urgency": "low",
        "confidence": 0.75,
        "summary": "Inquiry",
        "entities": {},
    })

    with patch.object(classifier.client, "generate", new=AsyncMock(return_value=cold_response)):
        result = await classifier.classify(msg, config)

    # "comprar" is a hot keyword → temperature should be overridden to hot
    assert result.lead_temperature == "hot"


@pytest.mark.asyncio
async def test_human_keyword_sets_entity():
    classifier = IntentClassifier()
    msg = _make_message("Quiero hablar con un asesor")
    config = _make_config()

    response = json.dumps({
        "intent": "support_request",
        "lead_temperature": "warm",
        "urgency": "medium",
        "confidence": 0.80,
        "summary": "Wants human",
        "entities": {},
    })

    with patch.object(classifier.client, "generate", new=AsyncMock(return_value=response)):
        result = await classifier.classify(msg, config)

    assert result.entities.get("_human_requested") is True


@pytest.mark.asyncio
async def test_fallback_model_used_on_primary_failure():
    from app.services.llm_client import LLMError

    classifier = IntentClassifier()
    msg = _make_message("Hola")
    config = _make_config()

    call_count = 0

    async def mock_generate(model, prompt, system=None, temperature=0.1, expect_json=True):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise LLMError("primary failed")
        return MOCK_CLASSIFICATION_RESPONSE

    with patch.object(classifier.client, "generate", side_effect=mock_generate):
        result = await classifier.classify(msg, config)

    assert call_count == 2  # primary + fallback
    assert result.intent == "pricing_request"


@pytest.mark.asyncio
async def test_invalid_intent_defaults_to_unknown():
    classifier = IntentClassifier()
    msg = _make_message("test")
    config = _make_config()

    bad_response = json.dumps({
        "intent": "INVALID_INTENT_XYZ",
        "lead_temperature": "warm",
        "urgency": "low",
        "confidence": 0.6,
        "summary": "test",
        "entities": {},
    })

    with patch.object(classifier.client, "generate", new=AsyncMock(return_value=bad_response)):
        result = await classifier.classify(msg, config)

    assert result.intent == "unknown"


@pytest.mark.asyncio
async def test_confidence_clamped():
    classifier = IntentClassifier()
    msg = _make_message("test")
    config = _make_config()

    bad_conf = json.dumps({
        "intent": "product_inquiry",
        "lead_temperature": "cold",
        "urgency": "low",
        "confidence": 9999,  # out of range
        "summary": "test",
        "entities": {},
    })

    with patch.object(classifier.client, "generate", new=AsyncMock(return_value=bad_conf)):
        result = await classifier.classify(msg, config)

    assert result.confidence == 1.0
