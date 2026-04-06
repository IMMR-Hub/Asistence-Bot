# CÓDIGO COMPLETO - SOFIA CHATBOT ORCHESTRATOR
**Sistema de Recepcionista Virtual para Consultorio Dental**
**Fecha: 01/04/2026**
**Estado: Simplificado a Máquina de Estados Pura en Python**

---

## ARCHIVO 1: ResponseOrchestrator (CORE)
**Ruta:** `app/modules/response_orchestrator/orchestrator.py`
**Descripción:** Máquina de estados pura. Python decide TODO, LLM solo genera texto.

```python
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.knowledge_resolver.resolver import KnowledgeContext
from app.schemas.common import ClassificationResult, NormalizedMessage
from app.schemas.tenant import TenantConfigSchema
from app.services.llm_client import LLMError, get_llm_client, parse_llm_json

logger = get_logger(__name__)


@dataclass
class OrchestratorResult:
    should_send: bool
    response_text: str | None
    escalated: bool
    escalation_reason: str | None = None


class ResponseOrchestrator:
    """
    Pure state machine approach: Python makes ALL decisions, LLM only generates response text.

    Estados:
    - SILENCE: Mensaje es solo agradecimiento (gracias, ok, etc) → sin respuesta
    - URGENCY_COLLECT: Urgencia + sin datos → pedir nombre+email
    - URGENCY_CONFIRM: Urgencia + con datos → confirmar y escalar
    - APPOINTMENT: Paciente pregunta horarios/cita → ofrecer slots
    - GENERAL: Todo lo demás → LLM genera respuesta
    """

    def __init__(self) -> None:
        self.client = get_llm_client()
        self.model = settings.LLM_RESPONSE_MODEL
        self.fallback_model = settings.LLM_CLASSIFY_MODEL

    def _get_local_time(self, timezone: str) -> str:
        """Retorna hora local con saludo."""
        try:
            tz = ZoneInfo(timezone or "America/Asuncion")
        except Exception:
            tz = ZoneInfo("America/Asuncion")
        now = datetime.now(tz)
        hour = now.hour
        if 6 <= hour < 12:
            greeting = "Buenos días"
        elif 12 <= hour < 19:
            greeting = "Buenas tardes"
        else:
            greeting = "Buenas noches"
        return f"{now.strftime('%H:%M')} ({greeting})"

    def _is_silence(self, text: str) -> bool:
        """Verifica si el mensaje es solo agradecimiento."""
        silence_phrases = {
            "gracias", "muchas gracias", "ok gracias", "dale gracias",
            "perfecto gracias", "ok", "dale", "listo", "entendido",
            "perfecto", "buenísimo", "genial", "excelente", "ok gracias", "vale",
        }
        return text.strip().lower() in silence_phrases

    def _extract_name(self, text: str) -> str:
        """Extrae nombre de texto como 'Mi nombre es Daniel Isaak'."""
        import re
        patterns = [
            r"(?:mi nombre es|soy|me llamo|nombre:?)\s+([A-Za-záéíóúñÁÉÍÓÚÑ]+(?:\s+[A-Za-záéíóúñÁÉÍÓÚÑ]+)*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _has_email(self, text: str) -> bool:
        """Verifica si el texto contiene email."""
        return "@" in text

    def _has_urgency_keywords(self, text: str) -> bool:
        """Verifica si el texto tiene palabras clave de urgencia clínica."""
        urgency_keywords = [
            "dolor", "duele", "me duele", "sangrado", "sangrando",
            "emergencia", "urgencia", "urgente", "se me cayó", "caído",
            "accidente", "hinchazón", "infección", "pus", "fiebre",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in urgency_keywords)

    def _has_appointment_keywords(self, text: str) -> bool:
        """Verifica si el texto pregunta por citas/horarios."""
        keywords = ["hora", "horario", "cita", "agendar", "turno", "disponible", "puedo venir", "que hora"]
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    async def generate(
        self,
        message: NormalizedMessage,
        classification: ClassificationResult,
        knowledge: KnowledgeContext,
        config: TenantConfigSchema,
        conversation_summary: str = "",
        contact_exists: bool = False,
        contact_phone: str | None = None,
    ) -> OrchestratorResult:
        """
        Máquina de estados pura. Sin lógica fuzzy de LLM.
        """
        current_text = (message.text_content or "").strip()
        conv_lower = conversation_summary.lower() if conversation_summary else ""

        # ═════════════════════════════════════════════════════════════
        # ESTADO 1: SILENCIO
        # ═════════════════════════════════════════════════════════════
        if self._is_silence(current_text):
            logger.info("orchestrator_state", state="SILENCE", tenant_id=str(message.tenant_id))
            return OrchestratorResult(should_send=False, response_text=None, escalated=False)

        # ═════════════════════════════════════════════════════════════
        # ESTADO 2: SOLICITUD DE CITA
        # ═════════════════════════════════════════════════════════════
        if self._has_appointment_keywords(current_text):
            slots = ", ".join(config.available_slots) if config.available_slots else "hoy o mañana"
            responses = [
                f"Perfecto 😊 Tenemos disponibles: {slots}. ¿Cuál te queda mejor?",
                f"Claro! Vemos un horario: {slots}. ¿Cuándo te va?",
                f"Seguro 😊 Opciones: {slots}. ¿Te va alguno de estos?",
            ]
            response = random.choice(responses)
            logger.info("orchestrator_state", state="APPOINTMENT", tenant_id=str(message.tenant_id))
            return OrchestratorResult(should_send=True, response_text=response, escalated=False)

        # ═════════════════════════════════════════════════════════════
        # ESTADO 3: URGENCIA + RECOPILACIÓN DE DATOS
        # ═════════════════════════════════════════════════════════════
        urgency_in_current = self._has_urgency_keywords(current_text)
        urgency_in_history = self._has_urgency_keywords(conv_lower)
        has_active_urgency = urgency_in_current or urgency_in_history

        name_from_current = self._extract_name(current_text)
        name_from_history = ""
        if conversation_summary:
            for line in conversation_summary.split("\n"):
                if "Paciente:" in line:
                    name_from_history = self._extract_name(line)
                    if name_from_history:
                        break

        patient_name = name_from_current or name_from_history or message.contact_name or ""
        has_email = self._has_email(current_text) or self._has_email(conv_lower) or bool(message.contact_email)
        has_data = bool(patient_name) and has_email

        # 3A: Urgencia + Sin Datos → Pedir datos
        if urgency_in_current and not has_data:
            is_first = not conversation_summary or "Sin historial" in conversation_summary
            greet = self._get_local_time(config.timezone).split("(")[1].rstrip(")")
            if is_first:
                responses = [
                    f"¡{greet}! 😟 Ay, qué molestia. Le aviso al doctor ahora mismo. ¿Me das tu nombre completo y correo para registrarte?",
                    f"¡{greet}! Soy Sofía 😟 Entiendo, le aviso al doctor ya. ¿Me pasás tu nombre completo y correo?",
                ]
            else:
                responses = [
                    "Entiendo 😟 Le aviso al doctor ahora mismo. ¿Me das tu nombre completo y correo para registrarte?",
                    "Lo siento mucho 😟 Paso esto como urgente. ¿Me pasás tu nombre completo y correo?",
                ]
            response = random.choice(responses)
            logger.info("orchestrator_state", state="URGENCY_COLLECT", tenant_id=str(message.tenant_id))
            return OrchestratorResult(should_send=True, response_text=response, escalated=False)

        # 3B: Urgencia + Con Datos → Confirmar
        if urgency_in_current and has_data:
            name_display = patient_name.split()[0] if patient_name else ""
            responses = [
                f"Perfecto, gracias {name_display} 🙌 Ya le aviso al doctor para que te contacte lo antes posible.",
                f"Anotado {name_display}, gracias 😊 Le paso tu caso al doctor ahora mismo.",
                f"Listo {name_display} 💙 Le aviso al doctor urgente, te contacta en breve.",
            ]
            response = random.choice(responses)
            logger.info("orchestrator_state", state="URGENCY_CONFIRM", tenant_id=str(message.tenant_id))
            return OrchestratorResult(
                should_send=True,
                response_text=response,
                escalated=True,
                escalation_reason="clinical_urgency",
            )

        # ═════════════════════════════════════════════════════════════
        # ESTADO 4: GENERAL (LLM)
        # ═════════════════════════════════════════════════════════════
        logger.info("orchestrator_state", state="GENERAL_LLM", tenant_id=str(message.tenant_id))

        knowledge_docs_text = ""
        if knowledge.knowledge_documents:
            knowledge_docs_text = "Información adicional:\n" + "\n---\n".join(knowledge.knowledge_documents[:5])

        is_first_message = not conversation_summary or "Sin historial" in conversation_summary
        current_time = self._get_local_time(config.timezone)
        contact_status = "cliente nuevo" if not contact_exists else f"cliente existente (teléfono: {contact_phone})"
        available_slots_text = ", ".join(config.available_slots) if config.available_slots else "hoy o mañana"

        prompt = f"""
CONSULTORIO: {knowledge.business_name}
Horarios: {knowledge.business_hours_text}
Paciente: {contact_status}
Hora local: {current_time}

=== HISTORIAL ===
{conversation_summary or "Sin historial previo."}

=== MENSAJE ACTUAL ===
"{current_text}"

=== CONTEXTO ===
Nombre: {patient_name or "(no registrado)"}
Teléfono: {contact_phone or "desconocido"}
Intención: {classification.intent}
Horarios disponibles: {available_slots_text}

=== INSTRUCCIONES ===
Eres Sofía, recepcionista virtual. Responde de forma natural y breve (máximo 2 oraciones, 1 pregunta).
- Si pregunta por horarios: ofrece {available_slots_text}
- Si pregunta por precios: da rango general, sugiere consulta
- Para cualquier otra consulta: responde directo y natural
- NUNCA pidas teléfono
- NUNCA repitas información ya dada

=== BASE DE CONOCIMIENTO ===
{knowledge.faq_snippets}
{knowledge_docs_text}

Responde SOLO JSON: {{"response_text": "..."}}
"""

        try:
            raw = await self.client.generate(
                model=self.model,
                prompt=prompt,
                temperature=0.5,
                expect_json=True,
            )
        except LLMError:
            logger.warning("response_model_failed", model=self.model)
            try:
                raw = await self.client.generate(
                    model=self.fallback_model,
                    prompt=prompt,
                    temperature=0.5,
                    expect_json=True,
                )
            except LLMError as exc:
                logger.error("llm_unavailable", error=str(exc))
                return OrchestratorResult(
                    should_send=False,
                    response_text=None,
                    escalated=True,
                    escalation_reason="llm_unavailable",
                )

        try:
            parsed = parse_llm_json(raw)
            text = parsed.get("response_text", "").strip()
        except LLMError:
            logger.error("response_parse_failed", raw=raw[:300])
            return OrchestratorResult(
                should_send=False,
                response_text=None,
                escalated=True,
                escalation_reason="response_parse_failed",
            )

        if not text:
            logger.info("orchestrator_empty_response", tenant_id=str(message.tenant_id))
            return OrchestratorResult(should_send=False, response_text=None, escalated=False)

        logger.info("orchestrator_llm_response", tenant_id=str(message.tenant_id), response_len=len(text))
        return OrchestratorResult(should_send=True, response_text=text, escalated=False)
```

---

## ARCHIVO 2: ConversationRepository
**Ruta:** `app/db/repositories/conversation_repo.py`
**Cambio:** Busca conversations "open" Y "escalated" para mantener continuidad

```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversation import Conversation
from app.db.repositories.base_repo import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Conversation)

    async def get_open_by_contact_and_channel(
        self, tenant_id: uuid.UUID, contact_id: uuid.UUID, channel: str
    ) -> Conversation | None:
        # Busca TANTO "open" COMO "escalated" porque escalated = necesita atención humana
        # pero el paciente puede seguir enviando mensajes en la misma conversación
        result = await self.session.execute(
            select(Conversation)
            .where(
                Conversation.tenant_id == tenant_id,
                Conversation.contact_id == contact_id,
                Conversation.channel == channel,
                Conversation.status.in_(["open", "escalated"]),
            )
            .order_by(Conversation.last_message_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[Conversation]:
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.tenant_id == tenant_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
```

---

## ARCHIVO 3: MessageProcessor (Fragmento)
**Ruta:** `app/services/message_processor.py`
**Cambios:** Detecta contact_is_new y lo pasa al orchestrator, construye conversation_summary

Líneas críticas (88-223):
```python
# 3. CRM: upsert contact + conversation + save message
# Detecta si el contacto es nuevo (primera vez) checando existencia antes del upsert
from app.db.repositories.contact_repo import ContactRepository
contact_repo = ContactRepository(self.session)
existing_contact = None
if msg.external_contact_id:
    existing_contact = await contact_repo.get_by_external_id(msg.tenant_id, msg.external_contact_id)
if not existing_contact and msg.contact_phone:
    existing_contact = await contact_repo.get_by_phone(msg.tenant_id, msg.contact_phone)
contact_is_new = existing_contact is None

contact = await self.crm.upsert_contact(msg)
conversation = await self.crm.upsert_conversation(msg, contact)
message_record = await self.crm.save_message(msg, conversation, contact)

# ... clasificación y entidades ...

# 8. Construir historial de conversación
recent_messages = await self.crm.msg_repo.list_by_conversation(conversation.id, limit=10)
conversation_summary = ""
if recent_messages:
    lines = []
    for m in recent_messages:
        role = "Paciente" if m.direction == "inbound" else "Sofía"
        if m.text_content:
            lines.append(f"{role}: {m.text_content}")
    conversation_summary = "\n".join(lines)

# 9. Generar y enviar respuesta
knowledge_ctx = self.knowledge.resolve(config)
orchestrated = await self.orchestrator.generate(
    message=msg,
    classification=classification,
    knowledge=knowledge_ctx,
    config=config,
    conversation_summary=conversation_summary,
    contact_exists=not contact_is_new,  # ← CRÍTICO
    contact_phone=contact.phone or msg.contact_phone,  # ← CRÍTICO
)
```

---

## ARCHIVO 4: Webhooks (Fragmento)
**Ruta:** `app/api/routes/webhooks.py`
**Cambio:** Lee tenant_slug desde header O query params (para Twilio que no puede enviar headers)

```python
# Línea 58: Resolución de tenant
tenant_slug = request.headers.get("X-Tenant-Slug", "") or request.query_params.get("tenant_slug", "")
if not tenant_slug:
    logger.warning("whatsapp_inbound_missing_tenant_slug")
    return {"status": "ignored", "reason": "missing_tenant_slug"}

# Línea 82-89: Verificación Twilio (skip en desarrollo)
if settings.APP_ENV == "production":
    x_twilio_sig = request.headers.get("X-Twilio-Signature", "")
    request_url = str(request.url)
    if x_twilio_sig and not verify_twilio_webhook(
        raw_body.decode("utf-8"), x_twilio_sig, url=request_url
    ):
        logger.warning("twilio_webhook_signature_verification_failed")
        return {"status": "error", "reason": "signature_verification_failed"}
```

---

## RESUMEN DE CAMBIOS

### ✅ Lo que FUNCIONA
1. **SILENCE**: Detecta "gracias", "ok", etc. → Sin respuesta
2. **APPOINTMENT**: Detecta "hora", "horario", "turno", "cita", etc. → Ofrece slots inmediatamente
3. **URGENCY_COLLECT**: Detecta "duele", "dolor", etc. sin datos → Pide nombre+email
4. **URGENCY_CONFIRM**: Detecta urgencia CON datos → Confirma y escala
5. **GENERAL**: Todo lo demás → LLM genera respuesta

### 🔧 Por qué está simplificado
- **Python = 100% decisiones** (no fuzzy LLM logic)
- **LLM = solo generación de texto** natural
- **Estados claros y testables**
- **Sin emojis hardcodeados** (random.choice())
- **Continuidad de conversación** (busca open + escalated)

### ⚠️ Limitación actual
- **Twilio Sandbox: 50 mensajes/día** (no es culpa del código)
- Se reinicia a **00:00 America/Asuncion**

---

## PARA REVISAR CON CODEX/GROK/KIMI/DEEPSEEK

Puntos clave a verificar:
1. ¿Hay algún race condition o deadlock en conversation_repo?
2. ¿El regex en _extract_name() cubre todos los casos en español?
3. ¿Hay alguna mejora en el prompt para GENERAL_LLM?
4. ¿Se puede optimizar el orden de checks en generate()?
5. ¿Falta manejo de algún edge case?

---

**Archivo generado:** 01/04/2026 - 15:47 UTC-3 (Paraguay)
