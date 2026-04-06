from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.lead import Lead
from app.db.repositories.base_repo import BaseRepository


class LeadRepository(BaseRepository[Lead]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Lead)

    async def get_open_lead_for_contact(
        self, tenant_id: uuid.UUID, contact_id: uuid.UUID
    ) -> Lead | None:
        stmt = (
            select(Lead)
            .where(
                Lead.tenant_id == tenant_id,
                Lead.contact_id == contact_id,
                Lead.status.in_(["new", "open", "in_progress"]),
            )
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[Lead]:
        result = await self.session.execute(
            select(Lead)
            .where(Lead.tenant_id == tenant_id)
            .order_by(Lead.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
