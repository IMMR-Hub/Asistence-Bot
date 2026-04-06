from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.knowledge_resolver.resolver import KnowledgeResolver
from app.modules.response_orchestrator.orchestrator import ResponseOrchestrator
from app.schemas.common import ClassificationResult, NormalizedMessage
from app.schemas.tenant import TenantConfigSchema


def _config() -> TenantConfigSchema:
    return TenantConfigSchema.model_validate({
        "tenant_slug": "x",
        "business_name": "ACME",
        "brand_tone": "friendly",
        "faq_entries": [],
        "follow_up_rules": [],
    })


def _msg() -> NormalizedMessage:
    return NormalizedMessage(
        message_id="m1",
        tenant_id=uuid.uuid4(),
        channel="whatsapp",
        direction="inbound",
        text_content="¿Tienen disponibilidad?",
        received_at=datetime.now(timezone.utc),
    )


def _cls() -> ClassificationResult:
    return ClassificationResult(
        intent="availability_check",
        lead_temperature="warm",
        urgency="medium",
        confidence=0.85,
        summary="Asking about availability",
        entities={},
    )


@pytest.mark.asyncio
async def test_response_generated_successfully():
    orch = ResponseOrchestrator()
    config = _config()
    knowledge = KnowledgeResolver().resolve(config)

    mock_resp = json.dumps({"response_text": "Hola, sí tenemos disponibilidad."})
    with patch.object(orch.client, "generate", new=AsyncMock(return_value=mock_resp)):
        result = await orch.generate(_msg(), _cls(), knowledge, config)

    assert result.should_send is True
    assert result.escalated is False
    assert "disponibilidad" in result.response_text


@pytest.mark.asyncio
async def test_escalation_when_both_models_fail():
    from app.services.llm_client import LLMError

    orch = ResponseOrchestrator()
    config = _config()
    knowledge = KnowledgeResolver().resolve(config)

    async def always_fail(*args, **kwargs):
        raise LLMError("model down")

    with patch.object(orch.client, "generate", side_effect=always_fail):
        result = await orch.generate(_msg(), _cls(), knowledge, config)

    assert result.should_send is False
    assert result.escalated is True
    assert result.escalation_reason == "llm_unavailable"


@pytest.mark.asyncio
async def test_escalation_on_empty_response():
    orch = ResponseOrchestrator()
    config = _config()
    knowledge = KnowledgeResolver().resolve(config)

    empty = json.dumps({"response_text": ""})
    with patch.object(orch.client, "generate", new=AsyncMock(return_value=empty)):
        result = await orch.generate(_msg(), _cls(), knowledge, config)

    assert result.should_send is False
    assert result.escalated is True
