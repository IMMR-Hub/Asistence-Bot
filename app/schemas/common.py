from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UUIDModel(ORMBase):
    id: uuid.UUID


class TimestampedModel(UUIDModel):
    created_at: datetime
    updated_at: datetime


class NormalizedMessage(BaseModel):
    """Channel-agnostic message schema — core contract."""

    message_id: str  # provider-issued or synthetic
    tenant_id: uuid.UUID
    channel: str  # whatsapp | email
    direction: str  # inbound | outbound
    external_contact_id: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    text_content: str | None = None
    attachments: list[dict[str, Any]] = []
    language: str | None = None
    received_at: datetime
    raw_payload: dict[str, Any] = {}


class ClassificationResult(BaseModel):
    intent: str
    lead_temperature: str
    urgency: str
    confidence: float
    summary: str
    entities: dict[str, Any] = {}
    # Behavioral flags (separate from intent)
    customer_requests_human: bool = False  # Customer explicitly asked for human
    clinical_urgency: bool = False  # Medical/clinical urgency (pain, bleeding, etc.)


class EntityExtractionResult(BaseModel):
    customer_name: str | None = None
    product_or_service_interest: str | None = None
    budget_hint: str | None = None
    location_hint: str | None = None
    preferred_contact_time: str | None = None
    language: str | None = None
