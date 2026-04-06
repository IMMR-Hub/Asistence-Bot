from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models.tenant import Tenant, TenantConfig
from app.schemas.common import NormalizedMessage
from app.services.message_processor import MessageProcessor


def _make_normalized(tenant_id: uuid.UUID, text: str, channel: str = "whatsapp") -> NormalizedMessage:
    return NormalizedMessage(
        message_id=f"test-{uuid.uuid4()}",
        tenant_id=tenant_id,
        channel=channel,
        direction="inbound",
        external_contact_id="595981111111",
        contact_name="Test User",
        contact_phone="595981111111",
        text_content=text,
        received_at=datetime.now(timezone.utc),
    )


async def _seed_tenant(db_session, slug: str, config_overrides: dict | None = None) -> Tenant:
    tenant = Tenant(
        tenant_slug=slug,
        business_name=f"Biz {slug}",
        timezone="UTC",
        default_language="es",
    )
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)

    config = {
        "tenant_slug": slug,
        "business_name": f"Biz {slug}",
        "timezone": "UTC",
        "default_language": "es",
        "enabled_channels": ["whatsapp", "email"],
        "enabled_modules": [
            "inbound_router", "intent_classifier", "crm_writer",
            "response_orchestrator", "knowledge_resolver",
            "follow_up_engine", "human_escalation", "audit_logger",
        ],
        "brand_tone": "professional",
        "business_hours": {"monday_to_friday": "08:00-18:00", "saturday": "closed", "sunday": "closed"},
        "faq_entries": [],
        "escalation_rules": {
            "confidence_threshold": 0.72,
            "always_escalate_hot_leads": False,
            "always_escalate_complaints": True,
        },
        "follow_up_rules": [
            {"rule_key": "test_rule", "delay_minutes": 60, "channel": "same_as_origin", "enabled": True}
        ],
        "classification_overrides": {"hot_keywords": ["comprar"], "human_request_keywords": ["asesor"]},
    }
    if config_overrides:
        config.update(config_overrides)

    cfg = TenantConfig(tenant_id=tenant.id, config_json=config, version=1, is_active=True)
    db_session.add(cfg)
    await db_session.flush()
    return tenant


GOOD_CLASSIFICATION = json.dumps({
    "intent": "product_inquiry",
    "lead_temperature": "warm",
    "urgency": "medium",
    "confidence": 0.90,
    "summary": "Customer asking about products",
    "entities": {"customer_name": "Test User", "language": "es"},
})

GOOD_RESPONSE = json.dumps({"response_text": "Hola, tenemos excelentes productos disponibles."})

LOW_CONF_CLASSIFICATION = json.dumps({
    "intent": "unknown",
    "lead_temperature": "cold",
    "urgency": "low",
    "confidence": 0.40,
    "summary": "Unclear message",
    "entities": {},
})

COMPLAINT_CLASSIFICATION = json.dumps({
    "intent": "complaint",
    "lead_temperature": "hot",
    "urgency": "high",
    "confidence": 0.95,
    "summary": "Customer complaint",
    "entities": {},
})


@pytest.mark.asyncio
async def test_full_autonomous_flow(db_session):
    """Classification → CRM → Response → Follow-up scheduled."""
    tenant = await _seed_tenant(db_session, "proc-test-auto")
    msg = _make_normalized(tenant.id, "¿Tienen madera de pino disponible?")

    with (
        patch("app.modules.intent_classifier.classifier.get_ollama_client") as mock_llm,
        patch("app.modules.response_orchestrator.orchestrator.get_ollama_client") as mock_llm2,
        patch("app.modules.follow_up_engine.engine.redis.from_url"),
    ):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=[GOOD_CLASSIFICATION, GOOD_RESPONSE])
        mock_llm.return_value = mock_client
        mock_llm2.return_value = mock_client

        processor = MessageProcessor(db_session)
        result = await processor.process(msg, send_fn=None)

    assert result.success is True
    assert result.escalated is False
    assert result.lead_id is not None
    assert result.conversation_id is not None
    assert result.message_id is not None
    assert result.response_text is not None


@pytest.mark.asyncio
async def test_escalation_on_low_confidence(db_session):
    """Low confidence → escalation created, no autonomous response."""
    tenant = await _seed_tenant(db_session, "proc-test-lowconf")
    msg = _make_normalized(tenant.id, "asdfghjkl")

    with (
        patch("app.modules.intent_classifier.classifier.get_ollama_client") as mock_llm,
        patch("app.modules.follow_up_engine.engine.redis.from_url"),
    ):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=LOW_CONF_CLASSIFICATION)
        mock_llm.return_value = mock_client

        processor = MessageProcessor(db_session)
        result = await processor.process(msg, send_fn=None)

    assert result.success is True
    assert result.escalated is True
    assert result.escalation_reason == "confidence_below_threshold"
    assert result.response_text is None


@pytest.mark.asyncio
async def test_escalation_on_complaint(db_session):
    """Complaint intent → always escalated regardless of confidence."""
    tenant = await _seed_tenant(db_session, "proc-test-complaint")
    msg = _make_normalized(tenant.id, "Estoy muy insatisfecho con el servicio")

    with (
        patch("app.modules.intent_classifier.classifier.get_ollama_client") as mock_llm,
        patch("app.modules.follow_up_engine.engine.redis.from_url"),
    ):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=COMPLAINT_CLASSIFICATION)
        mock_llm.return_value = mock_client

        processor = MessageProcessor(db_session)
        result = await processor.process(msg, send_fn=None)

    assert result.success is True
    assert result.escalated is True
    assert result.escalation_reason == "complaint_intent"


@pytest.mark.asyncio
async def test_tenant_isolation(db_session):
    """Tenant A config must not affect Tenant B processing."""
    tenant_a = await _seed_tenant(db_session, "tenant-a-iso", {"brand_tone": "formal"})
    tenant_b = await _seed_tenant(db_session, "tenant-b-iso", {"brand_tone": "casual"})

    msg_a = _make_normalized(tenant_a.id, "Hola desde tenant A")
    msg_b = _make_normalized(tenant_b.id, "Hola desde tenant B")

    from app.services.tenant_service import TenantService

    svc = TenantService(db_session)
    config_a = await svc.load_active_config(tenant_a.id)
    config_b = await svc.load_active_config(tenant_b.id)

    assert config_a is not None
    assert config_b is not None
    assert config_a.brand_tone == "formal"
    assert config_b.brand_tone == "casual"
    assert config_a.tenant_slug != config_b.tenant_slug


@pytest.mark.asyncio
async def test_crm_persistence_flow(db_session):
    """Contact, Conversation, Message, Lead created after processing."""
    from app.db.repositories.contact_repo import ContactRepository
    from app.db.repositories.lead_repo import LeadRepository

    tenant = await _seed_tenant(db_session, "proc-test-crm")
    msg = _make_normalized(tenant.id, "Quiero información sobre precios")

    with (
        patch("app.modules.intent_classifier.classifier.get_ollama_client") as mock_llm,
        patch("app.modules.response_orchestrator.orchestrator.get_ollama_client") as mock_llm2,
        patch("app.modules.follow_up_engine.engine.redis.from_url"),
    ):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=[GOOD_CLASSIFICATION, GOOD_RESPONSE])
        mock_llm.return_value = mock_client
        mock_llm2.return_value = mock_client

        processor = MessageProcessor(db_session)
        result = await processor.process(msg, send_fn=None)

    contact_repo = ContactRepository(db_session)
    contact = await contact_repo.get_by_phone(tenant.id, "595981111111")
    assert contact is not None
    assert contact.full_name == "Test User"

    lead_repo = LeadRepository(db_session)
    lead = await lead_repo.get_by_id(result.lead_id)
    assert lead is not None
    assert lead.source_channel == "whatsapp"
    assert lead.intent == "product_inquiry"
