from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.classification import LeadClassification
from app.db.repositories.base_repo import BaseRepository


class ClassificationRepository(BaseRepository[LeadClassification]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LeadClassification)

    async def get_by_message_id(self, message_id: uuid.UUID) -> LeadClassification | None:
        result = await self.session.execute(
            select(LeadClassification).where(LeadClassification.message_id == message_id)
        )
        return result.scalar_one_or_none()
