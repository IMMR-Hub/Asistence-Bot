from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.conversation_state import ConversationState
from app.modules.audit_logger.logger import AuditLogger
from app.modules.crm_writer.writer import CRMWriter
from app.modules.entity_extractor.extractor import EntityExtractor
from app.modules.follow_up_engine.engine import FollowUpEngine
from app.modules.human_escalation.escalation import HumanEscalation
from app.modules.intent_classifier.classifier import IntentClassifier
from app.modules.knowledge_resolver.resolver import KnowledgeResolver
from app.modules.response_orchestrator.orchestrator import ResponseOrchestrator
from app.schemas.common import NormalizedMessage
from app.schemas.tenant import TenantConfigSchema
from app.services.tenant_service import TenantService

logger = get_logger(__name__)


@dataclass
class ProcessingResult:
    success: bool
    message_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    escalated: bool = False
    escalation_reason: str | None = None
    response_sent: bool = False
    response_text: str | None = None
    errors: list[str] = field(default_factory=list)


class MessageProcessor:
    """
    Full inbound message processing pipeline:
    normalize → classify → extract → CRM → load memory → orchestrate →
    persist memory → escalate/book → respond → follow-up → audit
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tenant_service = TenantService(session)
        self.crm = CRMWriter(session)
        self.classifier = IntentClassifier()
        self.extractor = EntityExtractor()
        self.knowledge = KnowledgeResolver()
        self.orchestrator = ResponseOrchestrator()
        self.escalation_module = HumanEscalation(session)
        self.follow_up = FollowUpEngine(session)
        self.audit = AuditLogger(session)

    async def process(
        self,
        msg: NormalizedMessage,
        send_fn: Any = None,  # callable(tenant_id, contact, channel, text) → bool
    ) -> ProcessingResult:
        result = ProcessingResult(success=False)

        # ── 1. Resolve tenant config ─────────────────────────────────────────
        config = await self.tenant_service.load_active_config(msg.tenant_id)
        if config is None:
            logger.error("no_active_tenant_config", tenant_id=str(msg.tenant_id))
            result.errors.append("no_active_tenant_config")
            return result

        if msg.channel not in config.enabled_channels:
            logger.warning(
                "channel_not_enabled",
                channel=msg.channel,
                tenant_id=str(msg.tenant_id),
            )
            result.errors.append(f"channel_{msg.channel}_not_enabled")
            return result

        # ── 2. Audit inbound ─────────────────────────────────────────────────
        await self.audit.log(
            event_type="message_inbound",
            event_source=msg.channel,
            payload={"message_id": msg.message_id, "channel": msg.channel},
            tenant_id=msg.tenant_id,
        )

        # ── 3. CRM: upsert contact + conversation + save message ─────────────
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

        result.message_id = message_record.id
        result.conversation_id = conversation.id

        # ── 4. Classify ──────────────────────────────────────────────────────
        classification = await self.classifier.classify(msg, config)

        # ── 5. Extract entities ──────────────────────────────────────────────
        entities = self.extractor.extract_from_classification(classification)
        entities = self.extractor.merge_with_contact_data(
            entities,
            contact_name=msg.contact_name,
            contact_phone=msg.contact_phone,
            contact_email=msg.contact_email,
            language=msg.language,
        )

        # ── 6. CRM: upsert lead + save classification ────────────────────────
        lead = await self.crm.upsert_lead(msg, contact, classification)
        await self.crm.save_classification(
            tenant_id=msg.tenant_id,
            message_id=message_record.id,
            lead_id=lead.id,
            classification=classification,
            model_name=settings.LLM_CLASSIFY_MODEL,
        )
        result.lead_id = lead.id

        await self.audit.log(
            event_type="message_classified",
            event_source="intent_classifier",
            payload={
                "intent": classification.intent,
                "temperature": classification.lead_temperature,
                "confidence": classification.confidence,
                "lead_id": str(lead.id),
            },
            tenant_id=msg.tenant_id,
        )

        # ── 7. Load structured memory (single source of truth) ───────────────
        memory = conversation.get_memory()
        logger.info(
            "memory_loaded",
            state=memory.state if isinstance(memory.state, str) else memory.state.value,
            tenant_id=str(msg.tenant_id),
            conversation_id=str(conversation.id),
        )

        # ── 8. Orchestrate: state machine decides everything ──────────────────
        knowledge_ctx = self.knowledge.resolve(config)
        orchestrated = await self.orchestrator.generate(
            message=msg,
            classification=classification,
            knowledge=knowledge_ctx,
            config=config,
            memory=memory,
            contact_exists=not contact_is_new,
            contact_phone=contact.phone or msg.contact_phone,
            contact_email=contact.email or msg.contact_email,
        )

        # ── 9. Persist updated memory ─────────────────────────────────────────
        conversation.set_memory(orchestrated.memory)

        # ── 10. Handle state transitions in DB ───────────────────────────────
        new_state = (
            orchestrated.memory.state
            if isinstance(orchestrated.memory.state, ConversationState)
            else ConversationState(orchestrated.memory.state)
        )

        if orchestrated.escalated and not conversation.escalated:
            # First-time escalation: create record and mark conversation
            await self.escalation_module.create_escalation(
                tenant_id=msg.tenant_id,
                conversation_id=conversation.id,
                lead_id=lead.id,
                reason=orchestrated.escalation_reason or "orchestrator_escalation",
                summary=classification.summary,
            )
            conversation.mark_escalated()
            result.escalated = True
            result.escalation_reason = orchestrated.escalation_reason

        elif new_state == ConversationState.BOOKED and conversation.status != "booked":
            conversation.mark_booked()

        elif orchestrated.close_conversation and conversation.status not in {"closed"}:
            conversation.mark_closed()

        await self.session.flush()

        # ── 11. Send response ─────────────────────────────────────────────────
        if orchestrated.should_send and orchestrated.response_text:
            result.response_text = orchestrated.response_text
            if send_fn:
                try:
                    sent = await send_fn(
                        tenant_id=msg.tenant_id,
                        contact=contact,
                        channel=msg.channel,
                        text=orchestrated.response_text,
                    )
                    result.response_sent = bool(sent)
                except Exception as exc:
                    logger.error("send_failed", error=str(exc), tenant_id=str(msg.tenant_id))
                    result.errors.append(f"send_failed: {exc}")

        await self.audit.log(
            event_type="response_sent" if result.response_sent else "response_skipped",
            event_source="response_orchestrator",
            payload={
                "state": new_state.value,
                "should_send": orchestrated.should_send,
                "escalated": orchestrated.escalated,
                "response_len": len(orchestrated.response_text or ""),
                "channel": msg.channel,
            },
            tenant_id=msg.tenant_id,
        )

        # ── 12. Schedule follow-ups ───────────────────────────────────────────
        await self.follow_up.schedule_follow_ups(lead, conversation, config)

        result.success = True
        return result
