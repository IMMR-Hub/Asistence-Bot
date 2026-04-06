from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.inbound_router.router import InboundRouter
from app.schemas.common import NormalizedMessage
from app.schemas.webhook import EmailInboundPayload

logger = get_logger(__name__)

_router = InboundRouter()


def parse_email_inbound(payload: EmailInboundPayload, tenant_id: uuid.UUID) -> NormalizedMessage:
    """Convert normalised email payload into NormalizedMessage."""
    text = payload.text_content or ""
    # Strip basic HTML if only html_content provided
    if not text and payload.html_content:
        import re
        text = re.sub(r"<[^>]+>", " ", payload.html_content).strip()

    return _router.build_from_raw(
        message_id=payload.message_id or f"email-{uuid.uuid4()}",
        tenant_id=tenant_id,
        channel="email",
        direction="inbound",
        external_contact_id=payload.from_email,
        contact_name=payload.from_name,
        contact_email=payload.from_email,
        text_content=text or None,
        raw_payload=payload.model_dump(),
    )


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_name: str | None = None,
    from_email: str | None = None,
) -> bool:
    """Send outbound email via SMTP (TLS)."""
    import smtplib
    from email.mime.text import MIMEText
    from email.utils import formataddr

    host = settings.SMTP_HOST_OPTIONAL
    port = settings.SMTP_PORT_OPTIONAL
    username = settings.SMTP_USERNAME_OPTIONAL
    password = settings.SMTP_PASSWORD_OPTIONAL

    if not host or not username:
        logger.warning("smtp_send_skipped_missing_config")
        return False

    sender_email = from_email or username
    sender_display = from_name or sender_email

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_display, sender_email))
    msg["To"] = to_email

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if password:
                smtp.login(username, password)
            smtp.send_message(msg)
        logger.info("email_sent", to=to_email)
        return True
    except Exception as exc:
        logger.error("email_send_failed", error=str(exc), to=to_email)
        return False
