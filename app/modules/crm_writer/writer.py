from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.contact import Contact
from app.db.models.conversation import Conversation
from app.db.models.lead import Lead
from app.db.models.message import Message
from app.db.models.classification import LeadClassification
from app.db.repositories.contact_repo import ContactRepository
from app.db.repositories.conversation_repo import ConversationRepository
from app.db.repositories.lead_repo import LeadRepository
from app.db.repositories.message_repo import MessageRepository
from app.db.repositories.classification_repo import ClassificationRepository
from app.schemas.common import ClassificationResult, NormalizedMessage
from app.core.logging import get_logger

logger = get_logger(__name__)


class CRMWriter:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.contact_repo = ContactRepository(session)
        self.conv_repo = ConversationRepository(session)
        self.lead_repo = LeadRepository(session)
        self.msg_repo = MessageRepository(session)
        self.cls_repo = ClassificationRepository(session)

    async def upsert_contact(self, msg: NormalizedMessage) -> Contact:
        # Try by external_contact_id first (most reliable for WhatsApp)
        contact: Contact | None = None
        if msg.external_contact_id:
            contact = await self.contact_repo.get_by_external_id(
                msg.tenant_id, msg.external_contact_id
            )
        if not contact and msg.contact_phone:
            contact = await self.contact_repo.get_by_phone(msg.tenant_id, msg.contact_phone)
        if not contact and msg.contact_email:
            contact = await self.contact_repo.get_by_email(msg.tenant_id, msg.contact_email)

        if contact:
            # Update fields that may have improved
            if msg.contact_name and not contact.full_name:
                contact.full_name = msg.contact_name
            if msg.contact_phone and not contact.phone:
                contact.phone = msg.contact_phone
            if msg.contact_email and not contact.email:
                contact.email = msg.contact_email
            if msg.external_contact_id and not contact.external_contact_id:
                contact.external_contact_id = msg.external_contact_id
            await self.session.flush()
        else:
            contact = Contact(
                tenant_id=msg.tenant_id,
                external_contact_id=msg.external_contact_id,
                full_name=msg.contact_name,
                email=msg.contact_email,
                phone=msg.contact_phone,
                preferred_language=msg.language,
            )
            self.session.add(contact)
            await self.session.flush()
            await self.session.refresh(contact)

        return contact

    async def upsert_conversation(
        self, msg: NormalizedMessage, contact: Contact
    ) -> Conversation:
        conv = await self.conv_repo.get_open_by_contact_and_channel(
            msg.tenant_id, contact.id, msg.channel
        )
        if not conv:
            conv = Conversation(
                tenant_id=msg.tenant_id,
                contact_id=contact.id,
                channel=msg.channel,
                status="open",
                last_message_at=msg.received_at,
            )
            self.session.add(conv)
            await self.session.flush()
            await self.session.refresh(conv)
        else:
            conv.last_message_at = msg.received_at
            await self.session.flush()

        return conv

    async def save_message(
        self, msg: NormalizedMessage, conversation: Conversation, contact: Contact
    ) -> Message:
        # Idempotency: skip duplicate provider messages
        if msg.message_id:
            existing = await self.msg_repo.get_by_provider_message_id(msg.message_id)
            if existing:
                logger.info("duplicate_message_skipped", provider_message_id=msg.message_id)
                return existing

        message = Message(
            tenant_id=msg.tenant_id,
            conversation_id=conversation.id,
            contact_id=contact.id,
            direction=msg.direction,
            channel=msg.channel,
            message_type="text" if msg.text_content else "attachment",
            text_content=msg.text_content,
            attachments=msg.attachments if msg.attachments else None,
            provider_message_id=msg.message_id,
            raw_payload=msg.raw_payload,
        )
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def upsert_lead(
        self,
        msg: NormalizedMessage,
        contact: Contact,
        classification: ClassificationResult,
    ) -> Lead:
        lead = await self.lead_repo.get_open_lead_for_contact(msg.tenant_id, contact.id)
        now = datetime.now(timezone.utc)

        if lead:
            lead.intent = classification.intent
            lead.lead_temperature = classification.lead_temperature
            lead.urgency = classification.urgency
            lead.summary_text = classification.summary
            lead.last_activity_at = now
            await self.session.flush()
        else:
            lead = Lead(
                tenant_id=msg.tenant_id,
                contact_id=contact.id,
                source_channel=msg.channel,
                intent=classification.intent,
                lead_temperature=classification.lead_temperature,
                urgency=classification.urgency,
                status="new",
                summary_text=classification.summary,
                last_activity_at=now,
            )
            self.session.add(lead)
            await self.session.flush()
            await self.session.refresh(lead)

        return lead

    async def save_classification(
        self,
        tenant_id: uuid.UUID,
        message_id: uuid.UUID,
        lead_id: uuid.UUID,
        classification: ClassificationResult,
        model_name: str,
    ) -> LeadClassification:
        cls_record = LeadClassification(
            tenant_id=tenant_id,
            message_id=message_id,
            lead_id=lead_id,
            intent=classification.intent,
            lead_temperature=classification.lead_temperature,
            urgency=classification.urgency,
            confidence=classification.confidence,
            summary_text=classification.summary,
            entities=classification.entities,
            model_name=model_name,
        )
        self.session.add(cls_record)
        await self.session.flush()
        await self.session.refresh(cls_record)
        return cls_record
