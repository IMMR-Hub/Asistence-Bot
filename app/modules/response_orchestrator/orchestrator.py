from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.conversation_state import (
    ConversationMemory,
    ConversationState,
    ConversationStateEngine,
    EscalationReason,
    IntentKey,
    LastAction,
    LastQuestion,
    SlotOffer,
    TimeOfDayPreference,
)
from app.modules.knowledge_resolver.resolver import KnowledgeContext
from app.schemas.common import ClassificationResult, NormalizedMessage
from app.schemas.tenant import TenantConfigSchema
from app.services.llm_client import LLMError, get_llm_client, parse_llm_json

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Module-level compiled patterns (O(1) per message vs O(n) inline compilation)
# ─────────────────────────────────────────────────────────────────────────────

_EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# Lookahead stops name from absorbing the next keyword — "Juan, mi correo es..."
_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:mi nombre es|soy|me llamo|nombre:?)\s+"
    r"([A-Za-zÁÉÍÓÚÑáéíóúñ'\-]+(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñ'\-]+){0,3})"
    r"(?=\s+(?:y|mi correo|correo|email|mi número|mi numero|teléfono|telefono)\b|[.,;]|$)",
    re.IGNORECASE,
)

_PHONE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:(?:\+?595|0)\s?)?(?:9\d{2}[\s\-]?\d{3}[\s\-]?\d{3})"
)

_THANKS_ONLY: Final[frozenset[str]] = frozenset(
    {
        "gracias",
        "muchas gracias",
        "ok gracias",
        "perfecto gracias",
        "dale gracias",
        "genial gracias",
    }
)

_HUMAN_REQUEST_PATTERNS: Final[tuple[str, ...]] = (
    "quiero hablar con una persona",
    "quiero hablar con alguien",
    "quiero hablar con el doctor",
    "quiero que me llame el doctor",
    "quiero que me atienda una persona",
    "no quiero hablar con una máquina",
    "no quiero hablar con una maquina",
    "no quiero hablar con un bot",
)

_COMPLAINT_PATTERNS: Final[tuple[str, ...]] = (
    "me atendieron mal",
    "quiero hacer un reclamo",
    "quiero una solución",
    "quiero una solucion",
    "no me gustó la atención",
    "no me gusto la atencion",
    "estoy disconforme",
)

_URGENT_PATTERNS: Final[dict[EscalationReason, tuple[str, ...]]] = {
    EscalationReason.BLEEDING: ("sangrado", "me sangra", "sangrando", "encía sangra", "encia sangra"),
    EscalationReason.SWELLING: ("hinchazón", "hinchazon", "inflamado", "inflamada", "hinchado", "hinchada"),
    EscalationReason.FEVER: ("fiebre", "temperatura"),
    EscalationReason.BROKEN_TOOTH: ("se me rompió", "se me rompio", "diente roto", "muela rota", "golpe en el diente"),
    EscalationReason.URGENT_PAIN: ("dolor", "me duele", "dolor fuerte", "no aguanto el dolor", "urgencia", "urgente"),
    EscalationReason.HUMAN_REQUEST: _HUMAN_REQUEST_PATTERNS,
    EscalationReason.COMPLAINT: _COMPLAINT_PATTERNS,
}

_BOOKING_PATTERNS: Final[tuple[str, ...]] = (
    "agendar",
    "agenda",
    "turno",
    "cita",
    "limpieza",
    "consulta",
    "revisión",
    "revision",
    "chequeo",
    "evaluación",
    "evaluacion",
    "quiero ir",
    "hay lugar",
    "disponibilidad",
    "disponible",
)

_PRICE_PATTERNS: Final[tuple[str, ...]] = (
    "cuánto cuesta",
    "cuanto cuesta",
    "precio",
    "cuánto sale",
    "cuanto sale",
    "cuánto cobran",
    "cuanto cobran",
    "desde cuánto",
    "desde cuanto",
)

_MAX_LLM_TEXT_CHARS: Final[int] = 450


@dataclass(slots=True)
class OrchestratorResult:
    should_send: bool
    response_text: str | None
    escalated: bool
    escalation_reason: str | None
    memory: ConversationMemory
    close_conversation: bool = False


class ResponseOrchestrator:
    """
    Pure state machine: Python decides all routing and state transitions.
    LLM is invoked ONLY for free-text generation (general FAQ / price queries).

    States handled:
      NEW / COLLECTING_IDENTITY       → urgent identity collection
      URGENT_ESCALATED_WAITING        → silent or follow-up after escalation
      BOOKING_COLLECTING_PREFERENCE   → ask morning/afternoon once
      BOOKING_OFFERING_SLOTS          → offer slots, accept selection
      BOOKING_WAITING_CONFIRMATION    → ask confirmation, then book
      BOOKED / CLOSED                 → silent on "gracias"
      fallthrough                     → LLM general response
    """

    def __init__(self) -> None:
        self._engine = ConversationStateEngine()
        self._client = get_llm_client()
        self._response_model = settings.LLM_RESPONSE_MODEL
        self._response_timeout = int(getattr(settings, "LLM_TIMEOUT_SECONDS", 8))

    async def generate(
        self,
        *,
        message: NormalizedMessage,
        classification: ClassificationResult,
        knowledge: KnowledgeContext,
        config: TenantConfigSchema,
        memory: ConversationMemory | None = None,
        contact_exists: bool = False,
        contact_phone: str | None = None,
        contact_email: str | None = None,
    ) -> OrchestratorResult:
        current_memory = memory or ConversationMemory()
        latest_text = (message.text_content or "").strip()
        normalized_text = self._normalize_text(latest_text)

        # Hydrate memory with identity data from this message + contact record
        hydrated_memory = self._hydrate_memory_from_context(
            memory=current_memory,
            latest_text=latest_text,
            contact_name=message.contact_name,
            contact_phone=contact_phone or message.contact_phone,
            contact_email=contact_email or message.contact_email,
        )

        detected_intent = self._resolve_intent(
            text=normalized_text,
            classification=classification,
            current_state=hydrated_memory.state,
        )

        # ── Fast-path: terminal thanks in a silent state ─────────────────────
        if self._engine.is_terminal_thanks(normalized_text) and hydrated_memory.can_go_silent_on_thanks:
            return OrchestratorResult(
                should_send=False,
                response_text=None,
                escalated=hydrated_memory.urgent_escalated,
                escalation_reason=self._reason_str(hydrated_memory.escalation_reason),
                memory=hydrated_memory,
            )

        # ── Active state dispatch ────────────────────────────────────────────
        state = hydrated_memory.state if isinstance(hydrated_memory.state, ConversationState) else ConversationState(hydrated_memory.state)

        if state == ConversationState.URGENT_ESCALATED_WAITING:
            return await self._handle_urgent_escalated_waiting(
                text=latest_text,
                normalized_text=normalized_text,
                knowledge=knowledge,
                config=config,
                memory=hydrated_memory,
                detected_intent=detected_intent,
            )

        if state == ConversationState.BOOKING_COLLECTING_PREFERENCE:
            return self._handle_booking_collecting_preference(
                text=latest_text,
                config=config,
                memory=hydrated_memory,
            )

        if state == ConversationState.BOOKING_OFFERING_SLOTS:
            return self._handle_booking_offering_slots(
                text=latest_text,
                memory=hydrated_memory,
            )

        if state == ConversationState.BOOKING_WAITING_CONFIRMATION:
            return self._handle_booking_waiting_confirmation(
                message=message,
                text=latest_text,
                memory=hydrated_memory,
            )

        # ── State engine handles remaining transitions ───────────────────────
        decision = self._engine.decide(
            memory=hydrated_memory,
            latest_user_text=latest_text,
            detected_intent=detected_intent,
        )
        next_memory = self._engine.transition(memory=hydrated_memory, decision=decision)

        if decision.no_reply:
            return OrchestratorResult(
                should_send=False,
                response_text=None,
                escalated=next_memory.urgent_escalated,
                escalation_reason=self._reason_str(next_memory.escalation_reason),
                memory=next_memory,
            )

        # ── State: collecting identity (urgent needs data) ───────────────────
        next_state = next_memory.state if isinstance(next_memory.state, ConversationState) else ConversationState(next_memory.state)

        if next_state == ConversationState.COLLECTING_IDENTITY:
            response = self._render_identity_request(
                missing=next_memory.captured_identity.missing_for_urgent_escalation,
                config=config,
            )
            return OrchestratorResult(
                should_send=True,
                response_text=response,
                escalated=False,
                escalation_reason=None,
                memory=next_memory,
            )

        # ── State: urgent escalated (first confirmation) ─────────────────────
        if next_state == ConversationState.URGENT_ESCALATED_WAITING:
            if not next_memory.escalation_reason:
                reason = self._detect_escalation_reason(normalized_text)
                patched = next_memory.model_dump(mode="json")
                patched["escalation_reason"] = reason.value if reason else EscalationReason.UNKNOWN.value
                next_memory = ConversationMemory.model_validate(patched)

            response = self._render_urgent_escalation_confirmation(
                memory=next_memory,
                config=config,
            )
            return OrchestratorResult(
                should_send=True,
                response_text=response,
                escalated=True,
                escalation_reason=self._reason_str(next_memory.escalation_reason),
                memory=next_memory,
            )

        # ── Intent: enter booking flow ───────────────────────────────────────
        if detected_intent in {IntentKey.BOOK_APPOINTMENT, IntentKey.BOOK_CLEANING}:
            patched = next_memory.model_dump(mode="json")
            patched["state"] = ConversationState.BOOKING_COLLECTING_PREFERENCE.value
            patched["last_question_asked"] = LastQuestion.ASK_TIME_PREFERENCE.value
            patched["last_action"] = LastAction.OFFERED_TIME_PREFERENCE.value
            booking_memory = ConversationMemory.model_validate(patched)
            response = self._render_booking_preference_question(detected_intent)
            return OrchestratorResult(
                should_send=True,
                response_text=response,
                escalated=False,
                escalation_reason=None,
                memory=booking_memory,
            )

        # ── Intent: price inquiry ────────────────────────────────────────────
        if detected_intent == IntentKey.PRICE_INQUIRY:
            response = await self._render_price_response(
                text=latest_text,
                knowledge=knowledge,
                config=config,
                memory=next_memory,
            )
            return OrchestratorResult(
                should_send=True,
                response_text=response,
                escalated=False,
                escalation_reason=None,
                memory=next_memory,
            )

        # ── Fallthrough: general LLM response ────────────────────────────────
        response = await self._render_general_response(
            text=latest_text,
            classification=classification,
            knowledge=knowledge,
            config=config,
            memory=next_memory,
        )
        return OrchestratorResult(
            should_send=bool(response),
            response_text=response or None,
            escalated=False,
            escalation_reason=None,
            memory=next_memory,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Memory hydration
    # ─────────────────────────────────────────────────────────────────────────

    def _hydrate_memory_from_context(
        self,
        *,
        memory: ConversationMemory,
        latest_text: str,
        contact_name: str | None,
        contact_phone: str | None,
        contact_email: str | None,
    ) -> ConversationMemory:
        identity = memory.captured_identity.model_dump(mode="json")

        extracted_name = self._extract_name(latest_text) or (contact_name or "").strip() or None
        extracted_email = self._extract_email(latest_text) or contact_email or None
        extracted_phone = self._extract_phone(latest_text) or contact_phone or None

        # Only update fields not yet captured — never overwrite confirmed data
        if extracted_name and not identity.get("full_name"):
            identity["full_name"] = extracted_name
        if extracted_email and not identity.get("email"):
            identity["email"] = extracted_email
        if extracted_phone and not identity.get("phone"):
            identity["phone"] = extracted_phone

        return ConversationMemory.model_validate(
            {
                **memory.model_dump(mode="json"),
                "captured_identity": identity,
                "last_meaningful_user_message": latest_text,
            }
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Intent resolution
    # ─────────────────────────────────────────────────────────────────────────

    def _resolve_intent(
        self,
        *,
        text: str,
        classification: ClassificationResult,
        current_state: ConversationState | str,
    ) -> IntentKey:
        if self._matches_any(text, _HUMAN_REQUEST_PATTERNS):
            return IntentKey.HUMAN_ESCALATION
        if self._matches_any(text, _COMPLAINT_PATTERNS):
            return IntentKey.COMPLAINT
        if self._contains_urgency(text):
            return IntentKey.URGENT_PAIN
        if self._is_thanks_only(text):
            return IntentKey.THANKS_ONLY

        state_val = current_state.value if isinstance(current_state, ConversationState) else current_state
        if state_val in {
            ConversationState.BOOKING_COLLECTING_PREFERENCE.value,
            ConversationState.BOOKING_OFFERING_SLOTS.value,
            ConversationState.BOOKING_WAITING_CONFIRMATION.value,
        }:
            return IntentKey.BOOK_APPOINTMENT

        if self._contains_booking_request(text):
            if "limpieza" in text:
                return IntentKey.BOOK_CLEANING
            return IntentKey.BOOK_APPOINTMENT
        if self._contains_price_request(text):
            return IntentKey.PRICE_INQUIRY

        raw_intent = str(getattr(classification, "intent", "") or "").strip().lower()
        mapping = {
            "pricing_request": IntentKey.PRICE_INQUIRY,
            "appointment_request": IntentKey.BOOK_APPOINTMENT,
            "product_inquiry": IntentKey.GENERAL_FAQ,
            "support_request": IntentKey.GENERAL_FAQ,
            "complaint": IntentKey.COMPLAINT,
            "unknown": IntentKey.UNKNOWN,
        }
        return mapping.get(raw_intent, IntentKey.UNKNOWN)

    # ─────────────────────────────────────────────────────────────────────────
    # State handlers
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_urgent_escalated_waiting(
        self,
        *,
        text: str,
        normalized_text: str,
        knowledge: KnowledgeContext,
        config: TenantConfigSchema,
        memory: ConversationMemory,
        detected_intent: IntentKey,
    ) -> OrchestratorResult:
        reason_str = self._reason_str(memory.escalation_reason)

        if self._is_thanks_only(normalized_text):
            return OrchestratorResult(
                should_send=False,
                response_text=None,
                escalated=True,
                escalation_reason=reason_str,
                memory=memory,
            )

        if self._contains_booking_specific_question(normalized_text):
            return OrchestratorResult(
                should_send=True,
                response_text="Estoy revisando eso ahora mismo 😊 Si hay un espacio hoy, te lo confirmo por aquí.",
                escalated=True,
                escalation_reason=reason_str,
                memory=memory,
            )

        if detected_intent == IntentKey.BOOK_APPOINTMENT:
            patched = memory.model_dump(mode="json")
            patched["state"] = ConversationState.BOOKING_COLLECTING_PREFERENCE.value
            patched["last_question_asked"] = LastQuestion.ASK_TIME_PREFERENCE.value
            patched["last_action"] = LastAction.OFFERED_TIME_PREFERENCE.value
            # Reset urgent flags — user is now booking, not in crisis
            patched["urgent_escalated"] = False
            patched["awaiting_human_callback"] = False
            booking_memory = ConversationMemory.model_validate(patched)
            return OrchestratorResult(
                should_send=True,
                response_text="Sí, claro. ¿Te queda mejor por la mañana o por la tarde? 😊",
                escalated=True,
                escalation_reason=reason_str,
                memory=booking_memory,
            )

        response = await self._render_general_response(
            text=text,
            classification=ClassificationResult.model_validate(
                {
                    "intent": "support_request",
                    "lead_temperature": "warm",
                    "urgency": "medium",
                    "confidence": 0.8,
                    "summary": "follow-up after escalation",
                    "entities": {},
                }
            ),
            knowledge=knowledge,
            config=config,
            memory=memory,
        )
        return OrchestratorResult(
            should_send=bool(response),
            response_text=response or None,
            escalated=True,
            escalation_reason=reason_str,
            memory=memory,
        )

    def _handle_booking_collecting_preference(
        self,
        *,
        text: str,
        config: TenantConfigSchema,
        memory: ConversationMemory,
    ) -> OrchestratorResult:
        preference = self._engine.choose_time_preference(text)
        if preference is None:
            return OrchestratorResult(
                should_send=True,
                response_text="¿Te queda mejor por la mañana o por la tarde? 😊",
                escalated=False,
                escalation_reason=None,
                memory=memory,
            )

        slots = self._build_slot_offers(config=config, preference=preference)
        if not slots:
            patched = memory.model_dump(mode="json")
            patched["preferred_time_of_day"] = preference.value if hasattr(preference, "value") else str(preference)
            next_memory = ConversationMemory.model_validate(patched)
            return OrchestratorResult(
                should_send=True,
                response_text="Ahora mismo no tengo horarios disponibles en esa franja. Si quieres, te aviso apenas se libere uno 😊",
                escalated=False,
                escalation_reason=None,
                memory=next_memory,
            )

        patched = memory.model_dump(mode="json")
        patched["state"] = ConversationState.BOOKING_OFFERING_SLOTS.value
        patched["preferred_time_of_day"] = preference.value if hasattr(preference, "value") else str(preference)
        patched["offered_slots"] = [s.model_dump(mode="json") for s in slots]
        patched["last_question_asked"] = LastQuestion.OFFER_SLOTS.value
        patched["last_action"] = LastAction.OFFERED_SLOTS.value
        next_memory = ConversationMemory.model_validate(patched)

        offered = " o ".join(s.label for s in slots[:2])
        return OrchestratorResult(
            should_send=True,
            response_text=f"Perfecto 😊 Te puedo ofrecer {offered}. ¿Cuál te queda mejor?",
            escalated=False,
            escalation_reason=None,
            memory=next_memory,
        )

    def _handle_booking_offering_slots(
        self,
        *,
        text: str,
        memory: ConversationMemory,
    ) -> OrchestratorResult:
        selected = self._engine.find_selected_slot(text, memory.offered_slots)
        if selected is None:
            offered = " o ".join(s.label for s in memory.offered_slots[:2])
            return OrchestratorResult(
                should_send=True,
                response_text=f"Te puedo ofrecer {offered}. ¿Cuál prefieres? 😊",
                escalated=False,
                escalation_reason=None,
                memory=memory,
            )

        patched = memory.model_dump(mode="json")
        patched["state"] = ConversationState.BOOKING_WAITING_CONFIRMATION.value
        patched["selected_slot_id"] = selected.slot_id
        patched["selected_slot_label"] = selected.label
        patched["selected_slot_iso_datetime"] = selected.iso_datetime
        patched["last_question_asked"] = LastQuestion.ASK_BOOKING_CONFIRMATION.value
        patched["last_action"] = LastAction.REQUESTED_BOOKING_CONFIRMATION.value
        next_memory = ConversationMemory.model_validate(patched)

        if not next_memory.captured_identity.full_name:
            confirm_text = (
                f"Perfecto 😊 Te puedo agendar {selected.label}. "
                "¿Me compartes por favor tu nombre completo?"
            )
        else:
            confirm_text = (
                f"Perfecto 😊 Entonces te reservo {selected.label}. "
                "¿Te lo confirmo?"
            )
        return OrchestratorResult(
            should_send=True,
            response_text=confirm_text,
            escalated=False,
            escalation_reason=None,
            memory=next_memory,
        )

    def _handle_booking_waiting_confirmation(
        self,
        *,
        message: NormalizedMessage,
        text: str,
        memory: ConversationMemory,
    ) -> OrchestratorResult:
        enriched = self._hydrate_memory_from_context(
            memory=memory,
            latest_text=text,
            contact_name=message.contact_name,
            contact_phone=message.contact_phone,
            contact_email=message.contact_email,
        )

        if not enriched.captured_identity.full_name:
            return OrchestratorResult(
                should_send=True,
                response_text="Solo me falta tu nombre completo para dejar la cita registrada 😊",
                escalated=False,
                escalation_reason=None,
                memory=enriched,
            )

        if not self._engine.is_booking_confirmation(text):
            return OrchestratorResult(
                should_send=True,
                response_text=f"Si te parece bien, te confirmo {enriched.selected_slot_label} 😊",
                escalated=False,
                escalation_reason=None,
                memory=enriched,
            )

        patched = enriched.model_dump(mode="json")
        patched["state"] = ConversationState.BOOKED.value
        patched["no_reply_terminal"] = True
        patched["last_action"] = LastAction.CONFIRMED_BOOKING.value
        patched["last_question_asked"] = LastQuestion.NONE.value
        booked_memory = ConversationMemory.model_validate(patched)

        return OrchestratorResult(
            should_send=True,
            response_text=f"Perfecto, quedó agendada tu cita para {booked_memory.selected_slot_label} 😊",
            escalated=False,
            escalation_reason=None,
            memory=booked_memory,
            close_conversation=False,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Response renderers
    # ─────────────────────────────────────────────────────────────────────────

    def _render_identity_request(self, *, missing: list[str], config: TenantConfigSchema) -> str:
        greeting = self._time_greeting(config.timezone)
        human_missing = self._humanize_missing_fields(missing)
        return f"{greeting} 😟 Voy a ayudarte. ¿Me compartes por favor {human_missing}?"

    def _render_urgent_escalation_confirmation(
        self,
        *,
        memory: ConversationMemory,
        config: TenantConfigSchema,
    ) -> str:
        name = self._first_name(memory.captured_identity.full_name)
        options = [
            f"Perfecto, gracias {name} 😊 Ya lo paso con prioridad al doctor para que te contacten lo antes posible.",
            f"Gracias, {name} 🙌 Ya estoy derivando tu caso con prioridad.",
            f"Listo, {name}. Ya lo pasé como urgente para que te contacten cuanto antes.",
        ]
        return random.choice(options)

    def _render_booking_preference_question(self, detected_intent: IntentKey) -> str:
        if detected_intent == IntentKey.BOOK_CLEANING:
            return (
                "Perfecto 😊 Podemos ayudarte a agendar una limpieza y, si quieres, revisar también cómo están tus dientes. "
                "¿Te queda mejor por la mañana o por la tarde?"
            )
        return "Perfecto 😊 Te ayudo a agendar. ¿Te queda mejor por la mañana o por la tarde?"

    async def _render_price_response(
        self,
        *,
        text: str,
        knowledge: KnowledgeContext,
        config: TenantConfigSchema,
        memory: ConversationMemory,
    ) -> str:
        base = self._find_pricing_snippet(text)
        if base:
            return base
        return await self._render_general_response(
            text=text,
            classification=ClassificationResult.model_validate(
                {
                    "intent": "pricing_request",
                    "lead_temperature": "warm",
                    "urgency": "low",
                    "confidence": 0.85,
                    "summary": "pricing inquiry",
                    "entities": {},
                }
            ),
            knowledge=knowledge,
            config=config,
            memory=memory,
        )

    async def _render_general_response(
        self,
        *,
        text: str,
        classification: ClassificationResult,
        knowledge: KnowledgeContext,
        config: TenantConfigSchema,
        memory: ConversationMemory,
    ) -> str:
        # KnowledgeContext.faq_snippets is a pre-built string — use directly
        knowledge_snippets = knowledge.faq_snippets or ""
        docs = "\n---\n".join(knowledge.knowledge_documents[:2]) if knowledge.knowledge_documents else ""
        patient_name = memory.captured_identity.full_name or ""
        state_val = memory.state if isinstance(memory.state, str) else memory.state.value
        last_q_val = memory.last_question_asked if isinstance(memory.last_question_asked, str) else memory.last_question_asked.value
        last_a_val = memory.last_action if isinstance(memory.last_action, str) else memory.last_action.value

        prompt = f"""CONSULTORIO: {knowledge.business_name}
HORARIO: {knowledge.business_hours_text}
PACIENTE: {patient_name or "(sin nombre)"}
INTENT: {getattr(classification, "intent", "unknown")}
STATE: {state_val}
ULTIMA_PREGUNTA_HECHA: {last_q_val}
ULTIMA_ACCION: {last_a_val}

MENSAJE DEL PACIENTE:
{text}

REGLAS:
- Habla como una recepcionista real del consultorio.
- No digas que eres virtual.
- No te presentes de nuevo si la conversación ya está iniciada.
- Máximo 3 oraciones cortas.
- Máximo 1 pregunta.
- No repitas datos ya dados.
- Si el paciente pregunta algo concreto, responde eso primero.
- Si el paciente pide precio y no hay exactitud, usa "desde" y sugiere evaluación.
- Si ya se resolvió o se escaló, no sigas hablando de más.
- No uses frases robóticas ni administrativas.
- No superes {_MAX_LLM_TEXT_CHARS} caracteres.

FAQ / CONOCIMIENTO:
{knowledge_snippets}

DOCUMENTOS:
{docs}

Responde SOLO JSON:
{{"response_text": "..."}}"""

        try:
            raw = await self._client.generate(
                model=self._response_model,
                prompt=prompt,
                temperature=0.35,
                expect_json=True,
                timeout=self._response_timeout,
            )
            parsed = parse_llm_json(raw)
            response_text = str(parsed.get("response_text", "")).strip()
            return response_text[:_MAX_LLM_TEXT_CHARS].strip()
        except (LLMError, ValueError, TypeError):
            return self._fallback_general_response(text=text, knowledge=knowledge)

    def _fallback_general_response(self, *, text: str, knowledge: KnowledgeContext) -> str:
        lower = self._normalize_text(text)
        if "horario" in lower or "atienden" in lower:
            return f"{knowledge.business_hours_text} 😊"
        if "donde" in lower or "dirección" in lower or "direccion" in lower:
            return "Con gusto 😊 Te compartimos la ubicación exacta por aquí."
        return "Claro 😊 Cuéntame un poco más y te ayudo."

    def _find_pricing_snippet(self, text: str) -> str | None:
        """Demo pricing — in production drive this from TenantConfigSchema.faq_entries."""
        lower = self._normalize_text(text)
        if "carilla" in lower:
            return "Las carillas tienen un costo desde 1.500.000 Gs, según la evaluación 😊 Lo ideal es que el doctor revise tu caso. ¿Te gustaría agendar una consulta?"
        if "blanqueamiento" in lower:
            return "El blanqueamiento tiene un costo desde 700.000 Gs 😊 El valor exacto depende de la evaluación. ¿Quieres que te ayude a agendar?"
        if "limpieza" in lower:
            return "La limpieza dental tiene un costo desde 150.000 Gs 😊 También podemos agendar una revisión general en la misma consulta."
        if "ortodoncia" in lower or "bracket" in lower:
            return "La ortodoncia tiene un costo desde 2.500.000 Gs, según la evaluación 😊 ¿Querés que coordinemos una cita?"
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Slot builder
    # ─────────────────────────────────────────────────────────────────────────

    def _build_slot_offers(
        self,
        *,
        config: TenantConfigSchema,
        preference: TimeOfDayPreference,
    ) -> list[SlotOffer]:
        available = list(getattr(config, "available_slots", []) or [])
        if not available:
            return []

        pref_val = preference.value if hasattr(preference, "value") else str(preference)
        selected: list[str] = []
        for slot in available:
            norm = self._normalize_text(slot)
            if pref_val == "morning" and (
                "am" in norm or "mañana" in norm or "manana" in norm or self._slot_hour(slot) < 12
            ):
                selected.append(slot)
            elif pref_val == "afternoon" and (
                "pm" in norm or "tarde" in norm or self._slot_hour(slot) >= 12
            ):
                selected.append(slot)

        if not selected:
            selected = available[:2]

        return [
            SlotOffer(
                slot_id=f"slot_{i}_{self._normalize_text(s).replace(' ', '_')}",
                label=s,
                iso_datetime=s,
                available=True,
            )
            for i, s in enumerate(selected[:2], start=1)
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # Pure helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _reason_str(reason: EscalationReason | str | None) -> str | None:
        if reason is None:
            return None
        return reason if isinstance(reason, str) else reason.value

    @staticmethod
    def _slot_hour(slot_label: str) -> int:
        match = re.search(r"\b(\d{1,2})(?::\d{2})?\b", slot_label)
        if not match:
            return 99
        try:
            return int(match.group(1))
        except ValueError:
            return 99

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.strip().lower().split())

    @staticmethod
    def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
        return any(pattern in text for pattern in patterns)

    def _contains_urgency(self, text: str) -> bool:
        return any(pattern in text for patterns in _URGENT_PATTERNS.values() for pattern in patterns)

    def _contains_booking_request(self, text: str) -> bool:
        return self._matches_any(text, _BOOKING_PATTERNS)

    def _contains_price_request(self, text: str) -> bool:
        return self._matches_any(text, _PRICE_PATTERNS)

    def _contains_booking_specific_question(self, text: str) -> bool:
        return "hay lugar" in text or "tenés lugar" in text or "tenes lugar" in text or "disponible hoy" in text

    def _is_thanks_only(self, text: str) -> bool:
        return text in _THANKS_ONLY

    def _extract_name(self, text: str) -> str | None:
        match = _NAME_RE.search(text)
        if not match:
            return None
        return " ".join(match.group(1).strip().split())

    def _extract_email(self, text: str) -> str | None:
        match = _EMAIL_RE.search(text)
        return match.group(0) if match else None

    def _extract_phone(self, text: str) -> str | None:
        match = _PHONE_RE.search(text)
        return match.group(0) if match else None

    def _detect_escalation_reason(self, normalized_text: str) -> EscalationReason | None:
        for reason, patterns in _URGENT_PATTERNS.items():
            if self._matches_any(normalized_text, patterns):
                return reason
        return None

    @staticmethod
    def _first_name(full_name: str | None) -> str:
        if not full_name:
            return "gracias"
        return full_name.strip().split()[0]

    @staticmethod
    def _humanize_missing_fields(missing: list[str]) -> str:
        if missing == ["full_name"]:
            return "tu nombre completo"
        if missing == ["contact"]:
            return "un número de contacto o correo"
        if missing == ["full_name", "contact"]:
            return "tu nombre completo y un número de contacto o correo"
        return "los datos faltantes"

    @staticmethod
    def _time_greeting(timezone: str) -> str:
        try:
            tz = ZoneInfo(timezone or "America/Asuncion")
        except Exception:
            tz = ZoneInfo("America/Asuncion")
        hour = datetime.now(tz).hour
        if 6 <= hour < 12:
            return "Buenos días"
        if 12 <= hour < 19:
            return "Buenas tardes"
        return "Buenas noches"
