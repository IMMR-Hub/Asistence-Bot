from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditEvent
from app.db.repositories.base_repo import BaseRepository


class AuditRepository(BaseRepository[AuditEvent]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditEvent)

    async def log(
        self,
        event_type: str,
        event_source: str,
        payload: dict[str, Any],
        tenant_id: uuid.UUID | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            event_source=event_source,
            payload=payload,
        )
        self.session.add(event)
        await self.session.flush()
        return event
