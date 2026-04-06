from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.escalation import Escalation
from app.db.repositories.base_repo import BaseRepository


class EscalationRepository(BaseRepository[Escalation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Escalation)

    async def list_open_by_tenant(
        self, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[Escalation]:
        result = await self.session.execute(
            select(Escalation)
            .where(
                Escalation.tenant_id == tenant_id,
                Escalation.status == "open",
            )
            .order_by(Escalation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_tenant(
        self, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[Escalation]:
        result = await self.session.execute(
            select(Escalation)
            .where(Escalation.tenant_id == tenant_id)
            .order_by(Escalation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
