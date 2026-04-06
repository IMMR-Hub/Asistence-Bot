from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.lead import Lead
    from app.db.models.conversation import Conversation


class FollowUpJob(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "follow_up_jobs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    # pending | sent | cancelled | failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rq_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    lead: Mapped[Lead] = relationship("Lead", back_populates="follow_up_jobs")
    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="follow_up_jobs")

    def __repr__(self) -> str:
        return f"<FollowUpJob {self.id} status={self.status} scheduled={self.scheduled_for}>"
