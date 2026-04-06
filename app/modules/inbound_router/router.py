from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.common import NormalizedMessage
from app.core.logging import get_logger

logger = get_logger(__name__)

_SUPPORTED_CHANNELS = {"whatsapp", "email"}


class InboundRouter:
    """
    Receives inbound payloads from all supported channels and normalises
    them into NormalizedMessage. Channel-specific parsing lives in adapters;
    this module only validates the normalised result.
    """

    def validate(self, msg: NormalizedMessage) -> NormalizedMessage:
        if msg.channel not in _SUPPORTED_CHANNELS:
            raise ValueError(f"Unsupported channel: {msg.channel}")
        if not msg.text_content and not msg.attachments:
            raise ValueError("Message must have text_content or attachments")
        return msg

    def build_from_raw(
        self,
        *,
        message_id: str,
        tenant_id: uuid.UUID,
        channel: str,
        direction: str = "inbound",
        external_contact_id: str | None = None,
        contact_name: str | None = None,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        text_content: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        language: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> NormalizedMessage:
        msg = NormalizedMessage(
            message_id=message_id,
            tenant_id=tenant_id,
            channel=channel,
            direction=direction,
            external_contact_id=external_contact_id,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            text_content=text_content,
            attachments=attachments or [],
            language=language,
            received_at=datetime.now(timezone.utc),
            raw_payload=raw_payload or {},
        )
        return self.validate(msg)
