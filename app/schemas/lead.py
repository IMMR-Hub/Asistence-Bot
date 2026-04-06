from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import TimestampedModel


class LeadRead(TimestampedModel):
    tenant_id: uuid.UUID
    contact_id: uuid.UUID
    source_channel: str
    intent: str
    lead_temperature: str
    urgency: str
    status: str
    owner: str | None = None
    summary_text: str | None = None
    last_activity_at: datetime | None = None


class ClassificationRead(TimestampedModel):
    tenant_id: uuid.UUID
    message_id: uuid.UUID
    lead_id: uuid.UUID | None = None
    intent: str
    lead_temperature: str
    urgency: str
    confidence: float
    summary_text: str | None = None
    entities: dict[str, Any] = {}
    model_name: str


class EscalationRead(TimestampedModel):
    tenant_id: uuid.UUID
    lead_id: uuid.UUID | None = None
    conversation_id: uuid.UUID
    reason: str
    status: str
    summary_text: str | None = None
    resolved_at: datetime | None = None
