from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPKMixin, utcnow

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.contact import Contact
    from app.db.models.classification import LeadClassification


class Message(UUIDPKMixin, Base):
    __tablename__ = "messages"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # inbound | outbound
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True, unique=True
    )
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")
    contact: Mapped[Contact | None] = relationship("Contact")
    classification: Mapped[LeadClassification | None] = relationship(
        "LeadClassification", back_populates="message", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Message {self.id} dir={self.direction} ch={self.channel}>"
