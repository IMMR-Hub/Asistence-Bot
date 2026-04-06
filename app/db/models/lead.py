from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.tenant import Tenant
    from app.db.models.contact import Contact
    from app.db.models.classification import LeadClassification
    from app.db.models.escalation import Escalation
    from app.db.models.follow_up import FollowUpJob


class Lead(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_channel: Mapped[str] = mapped_column(String(32), nullable=False)
    intent: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    lead_temperature: Mapped[str] = mapped_column(String(32), nullable=False, default="cold")
    urgency: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", index=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="leads")
    contact: Mapped[Contact] = relationship("Contact", back_populates="leads")
    classifications: Mapped[list[LeadClassification]] = relationship(
        "LeadClassification", back_populates="lead", cascade="all, delete-orphan"
    )
    escalations: Mapped[list[Escalation]] = relationship(
        "Escalation", back_populates="lead"
    )
    follow_up_jobs: Mapped[list[FollowUpJob]] = relationship(
        "FollowUpJob", back_populates="lead", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Lead {self.id} intent={self.intent} temp={self.lead_temperature}>"
