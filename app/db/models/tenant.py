from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.contact import Contact
    from app.db.models.conversation import Conversation
    from app.db.models.lead import Lead


class Tenant(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    tenant_slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    default_language: Mapped[str] = mapped_column(String(10), default="es", nullable=False)
    industry_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships
    configs: Mapped[list[TenantConfig]] = relationship(
        "TenantConfig", back_populates="tenant", cascade="all, delete-orphan"
    )
    contacts: Mapped[list[Contact]] = relationship(
        "Contact", back_populates="tenant", cascade="all, delete-orphan"
    )
    leads: Mapped[list[Lead]] = relationship(
        "Lead", back_populates="tenant", cascade="all, delete-orphan"
    )
    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.tenant_slug}>"


class TenantConfig(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "tenant_configs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="configs")

    def __repr__(self) -> str:
        return f"<TenantConfig tenant={self.tenant_id} v={self.version}>"
