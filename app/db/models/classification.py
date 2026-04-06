from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.message import Message
    from app.db.models.lead import Lead


class LeadClassification(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "lead_classifications"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    lead_temperature: Mapped[str] = mapped_column(String(32), nullable=False)
    urgency: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)

    message: Mapped[Message] = relationship("Message", back_populates="classification")
    lead: Mapped[Lead | None] = relationship("Lead", back_populates="classifications")

    def __repr__(self) -> str:
        return f"<LeadClassification intent={self.intent} conf={self.confidence:.2f}>"
