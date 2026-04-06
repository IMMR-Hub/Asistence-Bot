from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.domain.conversation_state import ConversationMemory

if TYPE_CHECKING:
    from app.db.models.tenant import Tenant
    from app.db.models.contact import Contact
    from app.db.models.message import Message
    from app.db.models.escalation import Escalation
    from app.db.models.follow_up import FollowUpJob


class Conversation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open", index=True
    )  # open | escalated | booked | closed
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Structured conversational memory — single source of truth for state machine
    conversation_state_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
    # Mirrors ConversationMemory.awaiting_human_callback for fast DB queries
    awaiting_human_callback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="conversations")
    contact: Mapped[Contact] = relationship("Contact", back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    escalations: Mapped[list[Escalation]] = relationship(
        "Escalation", back_populates="conversation", cascade="all, delete-orphan"
    )
    follow_up_jobs: Mapped[list[FollowUpJob]] = relationship(
        "FollowUpJob", back_populates="conversation", cascade="all, delete-orphan"
    )

    # ──────────────────────────────────────────────────────────────
    # Memory helpers — structured state machine persistence
    # ──────────────────────────────────────────────────────────────

    def get_memory(self) -> ConversationMemory:
        """Deserialise conversation_state_payload into a validated ConversationMemory."""
        payload = self.conversation_state_payload or {}
        if not payload:
            return ConversationMemory()
        try:
            return ConversationMemory.model_validate(payload)
        except Exception:
            # Corrupt payload: reset to clean state rather than crash
            return ConversationMemory()

    def set_memory(self, memory: ConversationMemory) -> None:
        """Serialise memory back to JSON column and sync derived boolean flags."""
        self.conversation_state_payload = memory.model_dump(mode="json")
        self.awaiting_human_callback = memory.awaiting_human_callback
        self.touch()

    def merge_memory_patch(self, patch: dict[str, Any]) -> ConversationMemory:
        """Apply a partial patch dict to the current memory and persist it."""
        current = self.get_memory().model_dump(mode="json")
        current.update(patch)
        memory = ConversationMemory.model_validate(current)
        self.set_memory(memory)
        return memory

    # ──────────────────────────────────────────────────────────────
    # Status transitions
    # ──────────────────────────────────────────────────────────────

    def mark_escalated(self) -> None:
        self.status = "escalated"
        self.escalated = True
        self.awaiting_human_callback = True
        self.touch()

    def mark_booked(self) -> None:
        self.status = "booked"
        self.awaiting_human_callback = False
        self.touch()

    def mark_closed(self) -> None:
        self.status = "closed"
        self.escalated = False
        self.awaiting_human_callback = False
        self.touch()

    def reopen(self) -> None:
        self.status = "open"
        self.touch()

    def touch(self, when: datetime | None = None) -> None:
        self.last_message_at = when or datetime.now(timezone.utc)

    # ──────────────────────────────────────────────────────────────
    # Properties
    # ──────────────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self.status in {"open", "escalated", "booked"}

    # ──────────────────────────────────────────────────────────────
    # Factory
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def build_new(
        cls,
        *,
        tenant_id: uuid.UUID,
        contact_id: uuid.UUID,
        channel: str,
        external_thread_id: str | None = None,
        memory: ConversationMemory | None = None,
    ) -> "Conversation":
        state = memory or ConversationMemory()
        return cls(
            tenant_id=tenant_id,
            contact_id=contact_id,
            channel=channel,
            status="open",
            conversation_state_payload=state.model_dump(mode="json"),
            awaiting_human_callback=state.awaiting_human_callback,
        )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} channel={self.channel} status={self.status}>"
