from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.audit_repo import AuditRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """Persists every inbound event, outbound event, decision path, and model result."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = AuditRepository(session)

    async def log(
        self,
        event_type: str,
        event_source: str,
        payload: dict[str, Any],
        tenant_id: uuid.UUID | None = None,
    ) -> None:
        await self.repo.log(
            event_type=event_type,
            event_source=event_source,
            payload=payload,
            tenant_id=tenant_id,
        )
        logger.debug(
            "audit_event",
            event_type=event_type,
            event_source=event_source,
            tenant_id=str(tenant_id) if tenant_id else None,
        )
