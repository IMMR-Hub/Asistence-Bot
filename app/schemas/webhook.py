from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class WhatsAppInboundPayload(BaseModel):
    """Raw Meta WhatsApp Cloud API webhook payload."""

    object: str
    entry: list[dict[str, Any]]


class EmailInboundPayload(BaseModel):
    """Normalised email inbound payload (sent by email adapter/forwarder)."""

    tenant_slug: str
    from_email: str
    from_name: str | None = None
    to_email: str
    subject: str | None = None
    text_content: str | None = None
    html_content: str | None = None
    message_id: str | None = None  # SMTP Message-ID header
    raw_headers: dict[str, str] = {}


class TestProcessMessageRequest(BaseModel):
    """Internal testing endpoint payload."""

    tenant_slug: str
    channel: str
    contact_phone: str | None = None
    contact_email: str | None = None
    contact_name: str | None = None
    text_content: str
