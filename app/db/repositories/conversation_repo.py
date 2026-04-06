from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversation import Conversation
from app.db.repositories.base_repo import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Conversation)

    async def get_open_by_contact_and_channel(
        self, tenant_id: uuid.UUID, contact_id: uuid.UUID, channel: str
    ) -> Conversation | None:
        """
        Return the most recent active conversation for this contact + channel.
        Active = open | escalated | booked (patient can still send follow-up messages).
        """
        result = await self.session.execute(
            select(Conversation)
            .where(
                Conversation.tenant_id == tenant_id,
                Conversation.contact_id == contact_id,
                Conversation.channel == channel,
                Conversation.status.in_(["open", "escalated", "booked"]),
            )
            .order_by(Conversation.last_message_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_awaiting_human_callback(
        self, tenant_id: uuid.UUID, limit: int = 50
    ) -> list[Conversation]:
        """Return conversations that need human follow-up, ordered oldest-first."""
        result = await self.session.execute(
            select(Conversation)
            .where(
                Conversation.tenant_id == tenant_id,
                Conversation.awaiting_human_callback.is_(True),
            )
            .order_by(Conversation.last_message_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_tenant(
        self, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[Conversation]:
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.tenant_id == tenant_id)
            .order_by(Conversation.last_message_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
