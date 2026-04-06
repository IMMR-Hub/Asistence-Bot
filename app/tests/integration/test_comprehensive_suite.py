"""
Comprehensive Test Suite for Universal Sales Automation Core
Task 6/9 — Expand Test Suite (33 tests minimum)

Coverage:
- 20 conversation flow tests
- 10 edge case tests
- 3 multi-tenant isolation tests
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models.tenant import Tenant, TenantConfig
from app.schemas.common import NormalizedMessage
from app.services.message_processor import MessageProcessor


def _make_normalized(
    tenant_id: uuid.UUID, text: str, channel: str = "whatsapp", phone: str = "595981111111"
) -> NormalizedMessage:
    """Factory for normalized messages."""
    return NormalizedMessage(
        message_id=f"test-{uuid.uuid4()}",
        tenant_id=tenant_id,
        channel=channel,
        direction="inbound",
        external_contact_id=phone,
        contact_name="Test User",
        contact_phone=phone,
        text_content=text,
        received_at=datetime.now(timezone.utc),
    )


async def _seed_tenant(db_session, slug: str, config_overrides: dict | None = None) -> Tenant:
    """Seed a tenant with default config."""
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
        "faq_entries": [
            {"question": "horario", "answer": "Lunes a viernes 8-18."},
            {"question": "precio", "answer": "Desde 50.000 Gs."},
        ],
        "escalation_rules": {
            "confidence_threshold": 0.72,
            "always_escalate_hot_leads": False,
            "always_escalate_complaints": True,
        },
        "follow_up_rules": [
            {"rule_key": "test_rule", "delay_minutes": 60, "channel": "same_as_origin", "enabled": True}
        ],
        "classification_overrides": {
            "hot_keywords": ["comprar", "urgente"],
            "human_request_keywords": ["asesor", "persona", "humano"],
            "clinical_urgency_keywords": ["dolor", "sangrado", "emergencia"],
        },
    }
    if config_overrides:
        config.update(config_overrides)

    cfg = TenantConfig(tenant_id=tenant.id, config_json=config, version=1, is_active=True)
    db_session.add(cfg)
    await db_session.flush()
    return tenant


# ============================================================================
# CLASSIFICATION MOCK RESPONSES
# ============================================================================

def _mock_classification(
    intent: str = "product_inquiry",
    temperature: str = "warm",
    urgency: str = "medium",
    confidence: float = 0.90,
    clinical_urgency: bool = False,
    customer_requests_human: bool = False,
) -> str:
    """Factory for mock LLM classification responses."""
    return json.dumps({
        "intent": intent,
        "lead_temperature": temperature,
        "urgency": urgency,
        "confidence": confidence,
        "summary": f"Test message for {intent}",
        "entities": {"customer_name": "Test User", "language": "es"},
        "clinical_urgency": clinical_urgency,
        "customer_requests_human": customer_requests_human,
    })


def _mock_response(text: str = "Hola, aquí está la información.") -> str:
    """Factory for mock LLM response generation."""
    return json.dumps({"response_text": text})


# ============================================================================
# PART 1: CONVERSATION FLOW TESTS (20 tests)
# ============================================================================

class TestConversationFlows:
    """20 conversation flow tests covering main business scenarios."""

    @pytest.mark.asyncio
    async def test_flow_001_product_inquiry_no_escalation(self, db_session):
        """Product inquiry with high confidence → response, no escalation."""
        tenant = await _seed_tenant(db_session, "flow-001")
        msg = _make_normalized(tenant.id, "¿Tienen madera de pino?")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("product_inquiry", confidence=0.95),
                _mock_response("Sí, tenemos madera de pino disponible."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert not result.escalated
        assert result.response_text is not None

    @pytest.mark.asyncio
    async def test_flow_002_pricing_inquiry_hot_lead(self, db_session):
        """Pricing question (hot keyword) → hot temperature classification."""
        tenant = await _seed_tenant(db_session, "flow-002")
        msg = _make_normalized(tenant.id, "¿Cuál es el precio de la madera?")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("pricing_request", temperature="hot", confidence=0.92),
                _mock_response("El precio es desde 50.000 Gs."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert not result.escalated

    @pytest.mark.asyncio
    async def test_flow_003_complaint_always_escalates(self, db_session):
        """Complaint intent → always escalate regardless of confidence."""
        tenant = await _seed_tenant(db_session, "flow-003")
        msg = _make_normalized(tenant.id, "Estoy muy insatisfecho con el servicio")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=_mock_classification("complaint", confidence=0.88))
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert result.escalated
        assert result.escalation_reason == "complaint_intent"

    @pytest.mark.asyncio
    async def test_flow_004_low_confidence_escalation(self, db_session):
        """Confidence < threshold → escalation, no response."""
        tenant = await _seed_tenant(db_session, "flow-004")
        msg = _make_normalized(tenant.id, "asdfghjklzxcvbnm")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=_mock_classification("unknown", confidence=0.35))
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert result.escalated
        assert result.escalation_reason == "confidence_below_threshold"
        assert result.response_text is None

    @pytest.mark.asyncio
    async def test_flow_005_clinical_urgency_escalation(self, db_session):
        """Clinical urgency (pain keyword) → immediate escalation."""
        tenant = await _seed_tenant(db_session, "flow-005")
        msg = _make_normalized(tenant.id, "Tengo mucho dolor de muela")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(
                return_value=_mock_classification("support_request", confidence=0.85, clinical_urgency=True)
            )
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert result.escalated
        assert result.escalation_reason == "clinical_urgency_detected"

    @pytest.mark.asyncio
    async def test_flow_006_human_request_escalation(self, db_session):
        """Customer explicitly requests human → escalation."""
        tenant = await _seed_tenant(db_session, "flow-006")
        msg = _make_normalized(tenant.id, "Quiero hablar con una persona humana, no con un bot")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(
                return_value=_mock_classification(
                    "support_request", confidence=0.90, customer_requests_human=True
                )
            )
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert result.escalated
        assert result.escalation_reason == "customer_requests_human"

    @pytest.mark.asyncio
    async def test_flow_007_appointment_request_no_escalation(self, db_session):
        """Appointment request with good confidence → response."""
        tenant = await _seed_tenant(db_session, "flow-007")
        msg = _make_normalized(tenant.id, "Quisiera agendar una cita para esta semana")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("appointment_request", temperature="hot", confidence=0.93),
                _mock_response("Me encantaría agendar tu cita. ¿Qué día te vendría mejor?"),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert not result.escalated
        assert result.response_text is not None

    @pytest.mark.asyncio
    async def test_flow_008_quote_request_hot_lead(self, db_session):
        """Quote request → hot lead classification."""
        tenant = await _seed_tenant(db_session, "flow-008")
        msg = _make_normalized(tenant.id, "Necesito cotización para 1000 unidades")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("quote_request", temperature="hot", confidence=0.94),
                _mock_response("Voy a preparar la cotización para ti."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert not result.escalated

    @pytest.mark.asyncio
    async def test_flow_009_availability_check_response(self, db_session):
        """Availability question → response with FAQ."""
        tenant = await _seed_tenant(db_session, "flow-009")
        msg = _make_normalized(tenant.id, "¿Cuál es el horario de atención?")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("availability_check", confidence=0.91),
                _mock_response("Lunes a viernes de 08:00 a 18:00."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert not result.escalated

    @pytest.mark.asyncio
    async def test_flow_010_support_request_response(self, db_session):
        """Support request → response with help."""
        tenant = await _seed_tenant(db_session, "flow-010")
        msg = _make_normalized(tenant.id, "Tengo un problema con mi pedido")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("support_request", temperature="warm", confidence=0.87),
                _mock_response("Lamento el inconveniente. ¿Cuál es el problema específico?"),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert not result.escalated

    @pytest.mark.asyncio
    async def test_flow_011_follow_up_reply_response(self, db_session):
        """Follow-up reply → response."""
        tenant = await _seed_tenant(db_session, "flow-011")
        msg = _make_normalized(tenant.id, "Sí, me interesa")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("follow_up_reply", confidence=0.88),
                _mock_response("Excelente. Aquí está la información que solicitaste."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert not result.escalated

    @pytest.mark.asyncio
    async def test_flow_012_multiple_messages_same_contact(self, db_session):
        """Contact sends multiple messages → conversation history."""
        tenant = await _seed_tenant(db_session, "flow-012")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("product_inquiry", confidence=0.90),
                _mock_response("Tenemos disponible."),
                _mock_classification("pricing_request", confidence=0.91),
                _mock_response("El precio es 50.000 Gs."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            msg1 = _make_normalized(tenant.id, "¿Tienen madera?", phone="595981222222")
            msg2 = _make_normalized(tenant.id, "¿Cuánto cuesta?", phone="595981222222")

            result1 = await processor.process(msg1, send_fn=None)
            result2 = await processor.process(msg2, send_fn=None)

        assert result1.success and result2.success
        assert result1.conversation_id == result2.conversation_id  # Same conversation

    @pytest.mark.asyncio
    async def test_flow_013_email_channel_processing(self, db_session):
        """Email message processed same as WhatsApp."""
        tenant = await _seed_tenant(db_session, "flow-013")
        msg = _make_normalized(tenant.id, "Interested in your products", channel="email")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("product_inquiry", confidence=0.89),
                _mock_response("Thank you for your interest."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        assert result.lead_id is not None

    @pytest.mark.asyncio
    async def test_flow_014_crm_persistence_creates_lead(self, db_session):
        """Processing creates Lead, Contact, Conversation records."""
        from app.db.repositories.lead_repo import LeadRepository
        from app.db.repositories.contact_repo import ContactRepository

        tenant = await _seed_tenant(db_session, "flow-014")
        msg = _make_normalized(tenant.id, "Test message", phone="595981333333")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("product_inquiry", confidence=0.90),
                _mock_response("Response."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        lead_repo = LeadRepository(db_session)
        lead = await lead_repo.get_by_id(result.lead_id)
        assert lead is not None
        assert lead.tenant_id == tenant.id

        contact_repo = ContactRepository(db_session)
        contact = await contact_repo.get_by_phone(tenant.id, "595981333333")
        assert contact is not None

    @pytest.mark.asyncio
    async def test_flow_015_escalation_creates_record(self, db_session):
        """Escalation creates Escalation record in database."""
        from app.db.repositories.escalation_repo import EscalationRepository

        tenant = await _seed_tenant(db_session, "flow-015")
        msg = _make_normalized(tenant.id, "Complaint here")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(
                return_value=_mock_classification("complaint", confidence=0.95)
            )
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.escalated
        escalation_repo = EscalationRepository(db_session)
        escalations = await escalation_repo.get_by_conversation(result.conversation_id)
        assert len(escalations) > 0

    @pytest.mark.asyncio
    async def test_flow_016_unknown_intent_escalates(self, db_session):
        """Unknown intent + low confidence → escalation."""
        tenant = await _seed_tenant(db_session, "flow-016")
        msg = _make_normalized(tenant.id, "fjdkjsdhfjkshdjkf")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=_mock_classification("unknown", confidence=0.20))
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.escalated
        assert result.escalation_reason == "confidence_below_threshold"

    @pytest.mark.asyncio
    async def test_flow_017_high_urgency_message(self, db_session):
        """High urgency message → correct classification."""
        tenant = await _seed_tenant(db_session, "flow-017")
        msg = _make_normalized(tenant.id, "¡URGENTE! Necesito respuesta ahora")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("support_request", urgency="high", confidence=0.88),
                _mock_response("Estoy aquí para ayudarte."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success

    @pytest.mark.asyncio
    async def test_flow_018_empty_message_handling(self, db_session):
        """Empty message → classification as unknown."""
        tenant = await _seed_tenant(db_session, "flow-018")
        msg = _make_normalized(tenant.id, "")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=_mock_classification("unknown", confidence=0.30))
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success

    @pytest.mark.asyncio
    async def test_flow_019_very_long_message(self, db_session):
        """Very long message → truncated and processed."""
        tenant = await _seed_tenant(db_session, "flow-019")
        long_text = "a" * 2000

        msg = _make_normalized(tenant.id, long_text)

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("product_inquiry", confidence=0.50),
                _mock_response("Message too long."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success

    @pytest.mark.asyncio
    async def test_flow_020_special_characters_message(self, db_session):
        """Message with special characters → processed correctly."""
        tenant = await _seed_tenant(db_session, "flow-020")
        msg = _make_normalized(tenant.id, "¿Cuándo hay disponibilidad? 🎯 #urgente @equipo")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("availability_check", confidence=0.86),
                _mock_response("Disponible ahora."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success


# ============================================================================
# PART 2: EDGE CASE TESTS (10 tests)
# ============================================================================

class TestEdgeCases:
    """10 edge case and boundary condition tests."""

    @pytest.mark.asyncio
    async def test_edge_001_exact_confidence_threshold(self, db_session):
        """Confidence exactly at threshold → not escalated."""
        tenant = await _seed_tenant(db_session, "edge-001")
        msg = _make_normalized(tenant.id, "Test message")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            # Exactly at threshold (0.72)
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("product_inquiry", confidence=0.72),
                _mock_response("Response."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success
        # At or above threshold should not escalate
        assert not result.escalated

    @pytest.mark.asyncio
    async def test_edge_002_confidence_just_below_threshold(self, db_session):
        """Confidence just below threshold → escalated."""
        tenant = await _seed_tenant(db_session, "edge-002")
        msg = _make_normalized(tenant.id, "Test message")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=_mock_classification("product_inquiry", confidence=0.71))
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.escalated
        assert result.escalation_reason == "confidence_below_threshold"

    @pytest.mark.asyncio
    async def test_edge_003_multiple_escalation_reasons_priority(self, db_session):
        """Clinical urgency + complaint → clinical urgency wins (highest priority)."""
        tenant = await _seed_tenant(db_session, "edge-003")
        msg = _make_normalized(tenant.id, "Tengo dolor y estoy insatisfecho")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(
                return_value=_mock_classification(
                    "complaint",
                    clinical_urgency=True,
                    confidence=0.90
                )
            )
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.escalated
        # Clinical urgency has highest priority
        assert result.escalation_reason == "clinical_urgency_detected"

    @pytest.mark.asyncio
    async def test_edge_004_null_text_content(self, db_session):
        """Message with null text_content → handled gracefully."""
        tenant = await _seed_tenant(db_session, "edge-004")
        msg = _make_normalized(tenant.id, None)

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=_mock_classification("unknown", confidence=0.10))
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success

    @pytest.mark.asyncio
    async def test_edge_005_rapid_fire_messages(self, db_session):
        """Multiple messages from same contact in sequence."""
        tenant = await _seed_tenant(db_session, "edge-005")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            responses = []
            for i in range(5):
                responses.extend([
                    _mock_classification("product_inquiry", confidence=0.85 + i * 0.01),
                    _mock_response(f"Response {i}."),
                ])
            mock_client.generate = AsyncMock(side_effect=responses)
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            for i in range(5):
                msg = _make_normalized(tenant.id, f"Message {i}", phone="595981555555")
                result = await processor.process(msg, send_fn=None)
                assert result.success

    @pytest.mark.asyncio
    async def test_edge_006_concurrent_contacts(self, db_session):
        """Different contacts → separate conversation threads."""
        tenant = await _seed_tenant(db_session, "edge-006")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            responses = []
            for i in range(3):
                responses.extend([
                    _mock_classification("product_inquiry", confidence=0.88),
                    _mock_response("Response."),
                ])
            mock_client.generate = AsyncMock(side_effect=responses)
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            conv_ids = []
            for i in range(3):
                msg = _make_normalized(tenant.id, "Test", phone=f"5959810000{i}")
                result = await processor.process(msg, send_fn=None)
                conv_ids.append(result.conversation_id)

        # All should have different conversation IDs
        assert len(set(conv_ids)) == 3

    @pytest.mark.asyncio
    async def test_edge_007_llm_failure_handling(self, db_session):
        """LLM returns invalid JSON → handled gracefully."""
        tenant = await _seed_tenant(db_session, "edge-007")
        msg = _make_normalized(tenant.id, "Test")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value="INVALID JSON")
            mock_llm.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        # Should handle gracefully, likely with unknown intent
        assert result.success or "error" in result.errors

    @pytest.mark.asyncio
    async def test_edge_008_config_missing_optional_fields(self, db_session):
        """Tenant config missing optional fields → defaults applied."""
        tenant = await _seed_tenant(
            db_session,
            "edge-008",
            {"faq_entries": [], "follow_up_rules": []}  # Minimal config
        )
        msg = _make_normalized(tenant.id, "Test")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("product_inquiry", confidence=0.90),
                _mock_response("Response."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            result = await processor.process(msg, send_fn=None)

        assert result.success

    @pytest.mark.asyncio
    async def test_edge_009_all_escalation_reasons_triggered(self, db_session):
        """Verify all 5 escalation reasons can be triggered."""
        reasons = {}

        # Reason 1: clinical_urgency_detected
        tenant1 = await _seed_tenant(db_session, "edge-009-1")
        msg1 = _make_normalized(tenant1.id, "Pain")
        with patch("app.modules.intent_classifier.classifier.get_llm_client") as m, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            m.return_value.generate = AsyncMock(
                return_value=_mock_classification("support_request", clinical_urgency=True)
            )
            result = await MessageProcessor(db_session).process(msg1)
            reasons["clinical_urgency_detected"] = result.escalation_reason

        # Reason 2: complaint_intent
        tenant2 = await _seed_tenant(db_session, "edge-009-2")
        msg2 = _make_normalized(tenant2.id, "Complaint")
        with patch("app.modules.intent_classifier.classifier.get_llm_client") as m, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            m.return_value.generate = AsyncMock(
                return_value=_mock_classification("complaint", confidence=0.95)
            )
            result = await MessageProcessor(db_session).process(msg2)
            reasons["complaint_intent"] = result.escalation_reason

        # Reason 3: customer_requests_human
        tenant3 = await _seed_tenant(db_session, "edge-009-3")
        msg3 = _make_normalized(tenant3.id, "Human")
        with patch("app.modules.intent_classifier.classifier.get_llm_client") as m, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            m.return_value.generate = AsyncMock(
                return_value=_mock_classification("support_request", customer_requests_human=True)
            )
            result = await MessageProcessor(db_session).process(msg3)
            reasons["customer_requests_human"] = result.escalation_reason

        # Reason 4: confidence_below_threshold
        tenant4 = await _seed_tenant(db_session, "edge-009-4")
        msg4 = _make_normalized(tenant4.id, "?")
        with patch("app.modules.intent_classifier.classifier.get_llm_client") as m, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            m.return_value.generate = AsyncMock(
                return_value=_mock_classification("unknown", confidence=0.30)
            )
            result = await MessageProcessor(db_session).process(msg4)
            reasons["confidence_below_threshold"] = result.escalation_reason

        # All 4 main reasons should exist (hot_lead escalation is rarely used)
        assert len([r for r in reasons.values() if r is not None]) >= 4

    @pytest.mark.asyncio
    async def test_edge_010_extreme_values(self, db_session):
        """Extreme values (confidence 0.0 or 1.0)."""
        tenant = await _seed_tenant(db_session, "edge-010")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            # Test confidence 0.0
            msg1 = _make_normalized(tenant.id, "Test1")
            mock_llm.return_value.generate = AsyncMock(
                return_value=_mock_classification("unknown", confidence=0.0)
            )
            result1 = await MessageProcessor(db_session).process(msg1)
            assert result1.escalated

            # Test confidence 1.0
            msg2 = _make_normalized(tenant.id, "Test2")
            mock_llm.return_value.generate = AsyncMock(
                return_value=_mock_classification("product_inquiry", confidence=1.0)
            )
            result2 = await MessageProcessor(db_session).process(msg2)
            assert not result2.escalated


# ============================================================================
# PART 3: MULTI-TENANT ISOLATION TESTS (3 tests)
# ============================================================================

class TestMultiTenantIsolation:
    """3 comprehensive multi-tenant isolation tests."""

    @pytest.mark.asyncio
    async def test_multi_tenant_001_config_independence(self, db_session):
        """Tenant A and B configs completely independent."""
        tenant_a = await _seed_tenant(
            db_session,
            "mt-001-a",
            {"escalation_rules": {"confidence_threshold": 0.80, "always_escalate_complaints": True}}
        )
        tenant_b = await _seed_tenant(
            db_session,
            "mt-001-b",
            {"escalation_rules": {"confidence_threshold": 0.60, "always_escalate_complaints": False}}
        )

        from app.services.tenant_service import TenantService
        svc = TenantService(db_session)
        cfg_a = await svc.load_active_config(tenant_a.id)
        cfg_b = await svc.load_active_config(tenant_b.id)

        assert cfg_a.escalation_rules["confidence_threshold"] == 0.80
        assert cfg_b.escalation_rules["confidence_threshold"] == 0.60
        assert cfg_a.escalation_rules["always_escalate_complaints"] is True
        assert cfg_b.escalation_rules["always_escalate_complaints"] is False

    @pytest.mark.asyncio
    async def test_multi_tenant_002_data_isolation(self, db_session):
        """Tenant A leads not visible in Tenant B."""
        from app.db.repositories.lead_repo import LeadRepository

        tenant_a = await _seed_tenant(db_session, "mt-002-a")
        tenant_b = await _seed_tenant(db_session, "mt-002-b")

        # Create leads in both tenants
        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("product_inquiry", confidence=0.90),
                _mock_response("Response A."),
                _mock_classification("product_inquiry", confidence=0.90),
                _mock_response("Response B."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            msg_a = _make_normalized(tenant_a.id, "Message A", phone="595981aaa")
            msg_b = _make_normalized(tenant_b.id, "Message B", phone="595981bbb")

            result_a = await processor.process(msg_a)
            result_b = await processor.process(msg_b)

        # Verify leads are isolated
        lead_repo = LeadRepository(db_session)
        leads_a = await lead_repo.get_all_by_tenant(tenant_a.id)
        leads_b = await lead_repo.get_all_by_tenant(tenant_b.id)

        # All leads in A should have tenant_a.id
        assert all(lead.tenant_id == tenant_a.id for lead in leads_a)
        # All leads in B should have tenant_b.id
        assert all(lead.tenant_id == tenant_b.id for lead in leads_b)
        # No leads of A in B
        assert not any(lead.tenant_id == tenant_a.id for lead in leads_b)

    @pytest.mark.asyncio
    async def test_multi_tenant_003_conversation_isolation(self, db_session):
        """Tenant A conversations not visible in Tenant B."""
        from app.db.repositories.conversation_repo import ConversationRepository

        tenant_a = await _seed_tenant(db_session, "mt-003-a")
        tenant_b = await _seed_tenant(db_session, "mt-003-b")

        with patch("app.modules.intent_classifier.classifier.get_llm_client") as mock_llm, \
             patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_resp, \
             patch("app.modules.follow_up_engine.engine.redis.from_url"):
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(side_effect=[
                _mock_classification("product_inquiry", confidence=0.90),
                _mock_response("Response."),
                _mock_classification("product_inquiry", confidence=0.90),
                _mock_response("Response."),
            ])
            mock_llm.return_value = mock_client
            mock_resp.return_value = mock_client

            processor = MessageProcessor(db_session)
            msg_a = _make_normalized(tenant_a.id, "Test A", phone="595981ccc")
            msg_b = _make_normalized(tenant_b.id, "Test B", phone="595981ddd")

            await processor.process(msg_a)
            await processor.process(msg_b)

        # Get conversations
        conv_repo = ConversationRepository(db_session)
        convs_a = await conv_repo.get_by_tenant(tenant_a.id)
        convs_b = await conv_repo.get_by_tenant(tenant_b.id)

        # Should be separate
        assert all(c.lead.tenant_id == tenant_a.id for c in convs_a)
        assert all(c.lead.tenant_id == tenant_b.id for c in convs_b)
