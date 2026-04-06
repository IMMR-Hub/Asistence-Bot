from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.tenant import Tenant
    from app.db.models.conversation import Conversation
    from app.db.models.lead import Lead


class Contact(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "contacts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_contact_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    preferred_language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="contacts")
    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="contact"
    )
    leads: Mapped[list[Lead]] = relationship("Lead", back_populates="contact")

    def __repr__(self) -> str:
        return f"<Contact {self.full_name or self.phone or self.email}>"
