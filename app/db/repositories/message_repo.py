from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.message import Message
from app.db.repositories.base_repo import BaseRepository


class MessageRepository(BaseRepository[Message]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Message)

    async def get_by_provider_message_id(self, provider_message_id: str) -> Message | None:
        result = await self.session.execute(
            select(Message).where(Message.provider_message_id == provider_message_id)
        )
        return result.scalar_one_or_none()

    async def list_by_conversation(
        self, conversation_id: uuid.UUID, limit: int = 50
    ) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
