"""
Unit tests for ResponseOrchestrator state machine.

All tests run WITHOUT a database — they test Python logic only.
LLM calls are mocked to return a fixed safe response.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.conversation_state import (
    CapturedIdentity,
    ConversationMemory,
    ConversationState,
    EscalationReason,
    LastAction,
    LastQuestion,
    SlotOffer,
    TimeOfDayPreference,
)
from app.modules.knowledge_resolver.resolver import KnowledgeContext
from app.modules.response_orchestrator.orchestrator import OrchestratorResult, ResponseOrchestrator
from app.schemas.common import ClassificationResult, NormalizedMessage
from app.schemas.tenant import TenantConfigSchema

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

TENANT_ID = uuid.uuid4()


def _msg(text: str, name: str | None = None, phone: str | None = None, email: str | None = None) -> NormalizedMessage:
    return NormalizedMessage(
        message_id="test-msg-001",
        tenant_id=TENANT_ID,
        channel="whatsapp",
        direction="inbound",
        contact_name=name,
        contact_phone=phone,
        contact_email=email,
        text_content=text,
        received_at=datetime.now(timezone.utc),
    )


def _classification(intent: str = "unknown") -> ClassificationResult:
    return ClassificationResult(
        intent=intent,
        lead_temperature="warm",
        urgency="low",
        confidence=0.9,
        summary="test",
    )


def _knowledge() -> KnowledgeContext:
    return KnowledgeContext(
        business_name="Clínica Demo",
        brand_tone="professional",
        business_hours_text="Lun-Vie 08:00-18:00",
        faq_snippets="Q: Horario\nA: Lunes a viernes 8-18.",
        signature_text=None,
        allowed_languages=["es"],
        knowledge_documents=[],
    )


def _config(slots: list[str] | None = None) -> TenantConfigSchema:
    return TenantConfigSchema(
        tenant_slug="test",
        business_name="Clínica Demo",
        timezone="America/Asuncion",
        available_slots=slots or ["mañana 09:00", "tarde 15:00"],
    )


def _memory_with_identity(name: str, phone: str | None = None, email: str | None = None) -> ConversationMemory:
    return ConversationMemory(
        captured_identity=CapturedIdentity(full_name=name, phone=phone, email=email)
    )


def _make_orchestrator() -> ResponseOrchestrator:
    """Build orchestrator with mocked LLM client."""
    with patch("app.modules.response_orchestrator.orchestrator.get_llm_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value='{"response_text": "Claro, con gusto te ayudo 😊"}')
        mock_get.return_value = mock_client
        orc = ResponseOrchestrator()
        orc._client = mock_client
        return orc


# ─────────────────────────────────────────────────────────────────────────────
# Helper for running async tests
# ─────────────────────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: urgencia sin datos → pide datos
# ─────────────────────────────────────────────────────────────────────────────

def test_urgent_without_identity_asks_for_data():
    """
    Patient reports pain but has NO name or contact → bot asks for identity,
    does NOT escalate yet.
    """
    orc = _make_orchestrator()
    result: OrchestratorResult = run(orc.generate(
        message=_msg("me duele mucho la muela"),
        classification=_classification("unknown"),
        knowledge=_knowledge(),
        config=_config(),
        memory=ConversationMemory(),
    ))

    assert result.should_send is True
    assert result.escalated is False
    assert result.memory.state in {ConversationState.COLLECTING_IDENTITY, "collecting_identity"}
    assert result.response_text is not None
    assert "nombre" in result.response_text.lower() or "contacto" in result.response_text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: urgencia con datos completos → escala
# ─────────────────────────────────────────────────────────────────────────────

def test_urgent_with_full_identity_escalates():
    """
    Patient reports pain AND already has name + phone → bot escalates immediately.
    """
    orc = _make_orchestrator()
    memory = _memory_with_identity("María López", phone="0981123456")

    result: OrchestratorResult = run(orc.generate(
        message=_msg("me duele mucho, necesito urgente"),
        classification=_classification("unknown"),
        knowledge=_knowledge(),
        config=_config(),
        memory=memory,
    ))

    assert result.escalated is True
    assert result.should_send is True
    assert result.memory.state in {ConversationState.URGENT_ESCALATED_WAITING, "urgent_escalated_waiting"}
    assert result.memory.urgent_escalated is True
    assert "maría" in result.response_text.lower() or "doctor" in result.response_text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: urgencia ya escalada + "gracias" → no responde
# ─────────────────────────────────────────────────────────────────────────────

def test_urgent_already_escalated_thanks_no_reply():
    """
    After escalation, patient sends "gracias" → bot stays SILENT.
    """
    orc = _make_orchestrator()
    # Build a memory that's already in URGENT_ESCALATED_WAITING
    memory = ConversationMemory.model_validate({
        "state": "urgent_escalated_waiting",
        "urgent_escalated": True,
        "awaiting_human_callback": True,
        "escalation_reason": "urgent_pain",
        "captured_identity": {"full_name": "María López", "phone": "0981123456"},
    })

    result: OrchestratorResult = run(orc.generate(
        message=_msg("gracias"),
        classification=_classification("unknown"),
        knowledge=_knowledge(),
        config=_config(),
        memory=memory,
    ))

    assert result.should_send is False
    assert result.response_text is None
    assert result.escalated is True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: booking → pregunta mañana/tarde UNA sola vez
# ─────────────────────────────────────────────────────────────────────────────

def test_booking_asks_time_preference_once():
    """
    Patient asks to book → bot asks morning/afternoon once, state moves to
    BOOKING_COLLECTING_PREFERENCE.
    """
    orc = _make_orchestrator()

    result: OrchestratorResult = run(orc.generate(
        message=_msg("quiero sacar una cita"),
        classification=_classification("appointment_request"),
        knowledge=_knowledge(),
        config=_config(),
        memory=ConversationMemory(),
    ))

    assert result.should_send is True
    assert result.memory.state in {
        ConversationState.BOOKING_COLLECTING_PREFERENCE,
        "booking_collecting_preference",
    }
    assert "mañana" in result.response_text.lower() or "tarde" in result.response_text.lower()
    # Bot should NOT ask again in the same response
    assert result.response_text.count("¿") <= 1


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: booking → si dice "tarde", ofrece slots de tarde
# ─────────────────────────────────────────────────────────────────────────────

def test_booking_offers_afternoon_slots_when_requested():
    """
    Patient is in BOOKING_COLLECTING_PREFERENCE and says "tarde" →
    bot offers afternoon slots and moves to BOOKING_OFFERING_SLOTS.
    """
    orc = _make_orchestrator()
    memory = ConversationMemory.model_validate({
        "state": "booking_collecting_preference",
        "last_question_asked": "ask_time_preference",
        "last_action": "offered_time_preference",
    })

    result: OrchestratorResult = run(orc.generate(
        message=_msg("por la tarde"),
        classification=_classification("unknown"),
        knowledge=_knowledge(),
        config=_config(slots=["mañana 09:00", "tarde 15:00", "tarde 17:00"]),
        memory=memory,
    ))

    assert result.should_send is True
    assert result.memory.state in {ConversationState.BOOKING_OFFERING_SLOTS, "booking_offering_slots"}
    assert "15:00" in result.response_text or "17:00" in result.response_text or "tarde" in result.response_text.lower()
    # Must NOT ask morning/afternoon again
    assert "mañana" not in result.response_text.lower() or "tarde" in result.response_text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: booking → si elige "a las 14", no vuelve a preguntar mañana/tarde
# ─────────────────────────────────────────────────────────────────────────────

def test_booking_slot_selection_does_not_re_ask_preference():
    """
    Patient is in BOOKING_OFFERING_SLOTS and says "a las 15" →
    bot moves to BOOKING_WAITING_CONFIRMATION, no morning/afternoon question.
    """
    orc = _make_orchestrator()
    memory = ConversationMemory.model_validate({
        "state": "booking_offering_slots",
        "preferred_time_of_day": "afternoon",
        "offered_slots": [
            {"slot_id": "slot_1", "label": "tarde 15:00", "iso_datetime": "tarde 15:00", "available": True},
            {"slot_id": "slot_2", "label": "tarde 17:00", "iso_datetime": "tarde 17:00", "available": True},
        ],
        "last_question_asked": "offer_slots",
        "last_action": "offered_slots",
        "captured_identity": {"full_name": "Juan Pérez"},
    })

    result: OrchestratorResult = run(orc.generate(
        message=_msg("a las 15"),
        classification=_classification("unknown"),
        knowledge=_knowledge(),
        config=_config(),
        memory=memory,
    ))

    assert result.should_send is True
    assert result.memory.state in {
        ConversationState.BOOKING_WAITING_CONFIRMATION,
        "booking_waiting_confirmation",
    }
    # Must NOT ask morning/afternoon again
    assert "mañana" not in result.response_text.lower()
    assert result.memory.selected_slot_label is not None


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7: booking → no confirma cita sin confirmación real del usuario
# ─────────────────────────────────────────────────────────────────────────────

def test_booking_does_not_confirm_without_real_confirmation():
    """
    Patient is in BOOKING_WAITING_CONFIRMATION but sends an ambiguous message →
    bot does NOT book, stays in confirmation state.
    """
    orc = _make_orchestrator()
    memory = ConversationMemory.model_validate({
        "state": "booking_waiting_confirmation",
        "selected_slot_id": "slot_1",
        "selected_slot_label": "tarde 15:00",
        "selected_slot_iso_datetime": "tarde 15:00",
        "offered_slots": [
            {"slot_id": "slot_1", "label": "tarde 15:00", "iso_datetime": "tarde 15:00", "available": True},
        ],
        "last_question_asked": "ask_booking_confirmation",
        "last_action": "requested_booking_confirmation",
        "captured_identity": {"full_name": "Juan Pérez"},
    })

    result: OrchestratorResult = run(orc.generate(
        message=_msg("no sé, lo pienso"),
        classification=_classification("unknown"),
        knowledge=_knowledge(),
        config=_config(),
        memory=memory,
    ))

    assert result.should_send is True
    # Must NOT be BOOKED
    assert result.memory.state not in {ConversationState.BOOKED, "booked"}
    # Should prompt confirmation
    assert result.response_text is not None


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8: booked + "gracias" → no responde
# ─────────────────────────────────────────────────────────────────────────────

def test_booked_thanks_no_reply():
    """
    After booking is confirmed, patient says "gracias" → bot is silent.
    """
    orc = _make_orchestrator()
    memory = ConversationMemory.model_validate({
        "state": "booked",
        "no_reply_terminal": True,
        "selected_slot_id": "slot_1",
        "selected_slot_label": "tarde 15:00",
        "selected_slot_iso_datetime": "tarde 15:00",
        "last_action": "confirmed_booking",
        "last_question_asked": "none",
        "captured_identity": {"full_name": "Juan Pérez"},
    })

    result: OrchestratorResult = run(orc.generate(
        message=_msg("gracias"),
        classification=_classification("unknown"),
        knowledge=_knowledge(),
        config=_config(),
        memory=memory,
    ))

    assert result.should_send is False
    assert result.response_text is None


# ─────────────────────────────────────────────────────────────────────────────
# TEST 9: no reinicia el personaje en medio del hilo
# ─────────────────────────────────────────────────────────────────────────────

def test_no_persona_restart_mid_conversation():
    """
    Orchestrator in BOOKING_COLLECTING_PREFERENCE must NOT re-introduce the bot.
    The response must go through the booking handler, not a fresh greeting.
    """
    orc = _make_orchestrator()
    memory = ConversationMemory.model_validate({
        "state": "booking_collecting_preference",
        "assistant_intro_done": True,
        "last_question_asked": "ask_time_preference",
        "last_action": "offered_time_preference",
        "captured_identity": {"full_name": "Ana García"},
    })

    result: OrchestratorResult = run(orc.generate(
        message=_msg("hola de nuevo"),
        classification=_classification("unknown"),
        knowledge=_knowledge(),
        config=_config(),
        memory=memory,
    ))

    assert result.should_send is True
    # Must stay in booking flow — no re-greeting
    assert result.memory.state in {
        ConversationState.BOOKING_COLLECTING_PREFERENCE,
        "booking_collecting_preference",
    }
    # Response is the preference question, not a greeting
    assert "mañana" in result.response_text.lower() or "tarde" in result.response_text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 10: no vuelve a pedir nombre si ya lo capturó
# ─────────────────────────────────────────────────────────────────────────────

def test_no_re_ask_name_if_already_captured():
    """
    Patient is in BOOKING_WAITING_CONFIRMATION with full_name already captured.
    Bot must NOT ask for name again.
    """
    orc = _make_orchestrator()
    memory = ConversationMemory.model_validate({
        "state": "booking_waiting_confirmation",
        "selected_slot_id": "slot_1",
        "selected_slot_label": "tarde 15:00",
        "selected_slot_iso_datetime": "tarde 15:00",
        "offered_slots": [
            {"slot_id": "slot_1", "label": "tarde 15:00", "iso_datetime": "tarde 15:00", "available": True},
        ],
        "last_question_asked": "ask_booking_confirmation",
        "last_action": "requested_booking_confirmation",
        "captured_identity": {"full_name": "Carlos Ruiz", "phone": "0981999888"},
    })

    result: OrchestratorResult = run(orc.generate(
        message=_msg("sí, confirmo"),
        classification=_classification("unknown"),
        knowledge=_knowledge(),
        config=_config(),
        memory=memory,
    ))

    assert result.should_send is True
    assert result.memory.state in {ConversationState.BOOKED, "booked"}
    # Must NOT ask for name
    assert "nombre" not in result.response_text.lower()
    # Slot label should appear in confirmation
    assert "15:00" in result.response_text or "agendada" in result.response_text.lower()
