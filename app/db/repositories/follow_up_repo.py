from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.follow_up import FollowUpJob
from app.db.repositories.base_repo import BaseRepository


class FollowUpRepository(BaseRepository[FollowUpJob]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FollowUpJob)

    async def list_pending_due(self, now: datetime) -> list[FollowUpJob]:
        result = await self.session.execute(
            select(FollowUpJob).where(
                FollowUpJob.status == "pending",
                FollowUpJob.scheduled_for <= now,
            )
        )
        return list(result.scalars().all())

    async def list_by_lead(self, lead_id: uuid.UUID) -> list[FollowUpJob]:
        result = await self.session.execute(
            select(FollowUpJob).where(FollowUpJob.lead_id == lead_id)
        )
        return list(result.scalars().all())
