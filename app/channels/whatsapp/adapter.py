from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from typing import Any
from urllib.parse import parse_qs, urlencode

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.inbound_router.router import InboundRouter
from app.schemas.common import NormalizedMessage

logger = get_logger(__name__)

_router = InboundRouter()


def parse_meta_inbound(payload: dict[str, Any], tenant_id: uuid.UUID) -> list[NormalizedMessage]:
    """
    Parse Meta WhatsApp Cloud API webhook payload into NormalizedMessage list.
    A single webhook event can contain multiple messages across multiple entries.
    """
    messages: list[NormalizedMessage] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if change.get("field") != "messages":
                continue

            contacts_map: dict[str, str] = {}
            for c in value.get("contacts", []):
                contacts_map[c.get("wa_id", "")] = c.get("profile", {}).get("name", "")

            for raw_msg in value.get("messages", []):
                wa_id = raw_msg.get("from", "")
                contact_name = contacts_map.get(wa_id)
                msg_type = raw_msg.get("type", "text")
                text_content: str | None = None
                attachments: list[dict[str, Any]] = []

                if msg_type == "text":
                    text_content = raw_msg.get("text", {}).get("body", "")
                elif msg_type in ("image", "audio", "video", "document", "sticker"):
                    media = raw_msg.get(msg_type, {})
                    attachments = [{"type": msg_type, "metadata": media}]
                    text_content = media.get("caption") or None
                elif msg_type == "interactive":
                    interactive = raw_msg.get("interactive", {})
                    if interactive.get("type") == "button_reply":
                        text_content = interactive["button_reply"].get("title", "")
                    elif interactive.get("type") == "list_reply":
                        text_content = interactive["list_reply"].get("title", "")

                if not text_content and not attachments:
                    logger.debug("skipping_unsupported_message_type", msg_type=msg_type)
                    continue

                try:
                    msg = _router.build_from_raw(
                        message_id=raw_msg.get("id", ""),
                        tenant_id=tenant_id,
                        channel="whatsapp",
                        direction="inbound",
                        external_contact_id=wa_id,
                        contact_name=contact_name,
                        contact_phone=wa_id,
                        text_content=text_content,
                        attachments=attachments,
                        raw_payload=raw_msg,
                    )
                    messages.append(msg)
                except ValueError as exc:
                    logger.warning("message_validation_failed", error=str(exc))

    return messages


async def send_whatsapp_message(
    to_phone: str,
    text: str,
    phone_number_id: str | None = None,
    access_token: str | None = None,
    provider: str | None = None,
    account_sid: str | None = None,
    auth_token: str | None = None,
    from_number: str | None = None,
) -> bool:
    """
    Send outbound WhatsApp text message.
    Dispatcher that routes to Meta or Twilio based on provider.
    """
    provider = provider or settings.WHATSAPP_PROVIDER

    if provider == "twilio":
        return await send_twilio_whatsapp_message(
            to_phone=to_phone,
            text=text,
            account_sid=account_sid,
            auth_token=auth_token,
            from_number=from_number,
        )
    else:
        return await send_meta_whatsapp_message(
            to_phone=to_phone,
            text=text,
            phone_number_id=phone_number_id,
            access_token=access_token,
        )


async def send_meta_whatsapp_message(
    to_phone: str,
    text: str,
    phone_number_id: str | None = None,
    access_token: str | None = None,
) -> bool:
    """Send outbound WhatsApp text message via Meta Cloud API."""
    import httpx

    pid = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    token = access_token or settings.WHATSAPP_ACCESS_TOKEN

    if not pid or not token:
        logger.warning("whatsapp_send_skipped_missing_credentials", provider="meta")
        return False

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    url = f"https://graph.facebook.com/v19.0/{pid}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info("whatsapp_message_sent", to=to_phone[:6] + "***", provider="meta")
            return True
        except httpx.HTTPStatusError as exc:
            logger.error(
                "whatsapp_send_failed",
                status=exc.response.status_code,
                body=exc.response.text[:200],
                provider="meta",
            )
            return False
        except httpx.RequestError as exc:
            logger.error("whatsapp_send_error", error=str(exc), provider="meta")
            return False


async def send_twilio_whatsapp_message(
    to_phone: str,
    text: str,
    account_sid: str | None = None,
    auth_token: str | None = None,
    from_number: str | None = None,
) -> bool:
    """Send outbound WhatsApp text message via Twilio API."""
    import httpx
    import base64

    sid = account_sid or settings.TWILIO_ACCOUNT_SID_OPTIONAL
    token = auth_token or settings.TWILIO_AUTH_TOKEN_OPTIONAL
    from_num = from_number or settings.TWILIO_WHATSAPP_NUMBER_OPTIONAL

    if not sid or not token or not from_num:
        logger.warning("twilio_whatsapp_send_skipped_missing_credentials", provider="twilio")
        return False

    # Normalize phone numbers for Twilio (format: whatsapp:+1234567890)
    to_formatted = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
    from_formatted = from_num if from_num.startswith("whatsapp:") else f"whatsapp:{from_num}"

    payload = {
        "From": from_formatted,
        "To": to_formatted,
        "Body": text,
    }

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    auth_str = f"{sid}:{token}"
    auth_bytes = auth_str.encode("utf-8")
    auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Convert payload to form-encoded (Twilio expects this, not JSON)
    form_data = urlencode(payload)

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, content=form_data, headers=headers)
            resp.raise_for_status()
            logger.info("twilio_whatsapp_message_sent", to=to_phone[:6] + "***", provider="twilio")
            return True
        except httpx.HTTPStatusError as exc:
            logger.error(
                "twilio_whatsapp_send_failed",
                status=exc.response.status_code,
                body=exc.response.text[:200],
                provider="twilio",
            )
            return False
        except httpx.RequestError as exc:
            logger.error("twilio_whatsapp_send_error", error=str(exc), provider="twilio")
            return False


def parse_twilio_inbound(
    payload: dict[str, Any] | str, tenant_id: uuid.UUID
) -> list[NormalizedMessage]:
    """
    Parse Twilio WhatsApp webhook payload into NormalizedMessage list.
    Twilio sends form-encoded data, which is converted to dict here.
    """
    messages: list[NormalizedMessage] = []

    # If payload is string (form-encoded), parse it
    if isinstance(payload, str):
        parsed = parse_qs(payload)
        payload = {k: v[0] if isinstance(v, list) and v else v for k, v in parsed.items()}

    # Validate this is a message event
    if payload.get("EventType") and payload.get("EventType") != "inbound-message":
        logger.debug("twilio_event_not_message", event_type=payload.get("EventType"))
        return messages

    # Extract message fields
    from_number = payload.get("From", "")
    contact_name = payload.get("ProfileName") or None
    text_content = payload.get("Body", "").strip() or None
    message_id = payload.get("MessageSid", f"twilio-{uuid.uuid4()}")
    attachments: list[dict[str, Any]] = []

    # Handle media attachments
    num_media = int(payload.get("NumMedia", 0))
    for i in range(num_media):
        media_url = payload.get(f"MediaUrl{i}")
        media_type = payload.get(f"MediaContentType{i}", "").split("/")[0]
        if media_url:
            attachments.append(
                {
                    "type": media_type or "file",
                    "url": media_url,
                    "content_type": payload.get(f"MediaContentType{i}"),
                }
            )

    if not text_content and not attachments:
        logger.debug("twilio_message_no_content")
        return messages

    try:
        msg = _router.build_from_raw(
            message_id=message_id,
            tenant_id=tenant_id,
            channel="whatsapp",
            direction="inbound",
            external_contact_id=from_number,
            contact_name=contact_name,
            contact_phone=from_number,
            text_content=text_content,
            attachments=attachments,
            raw_payload=payload,
        )
        messages.append(msg)
    except ValueError as exc:
        logger.warning("twilio_message_validation_failed", error=str(exc))

    return messages


def verify_twilio_webhook(
    request_body: str,
    signature: str,
    auth_token: str | None = None,
    url: str = "",
) -> bool:
    """
    Verify Twilio webhook signature.
    Twilio signs requests with HMAC-SHA1 using the auth token.
    """
    token = auth_token or settings.TWILIO_AUTH_TOKEN_OPTIONAL
    if not token:
        logger.warning("twilio_verification_skipped_no_token")
        return True  # Allow if not configured

    # Build signed data: URL + request body
    signed_data = url + request_body

    # Compute expected signature
    expected_sig = base64.b64encode(
        hmac.new(
            token.encode("utf-8"),
            signed_data.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("utf-8")

    # Compare
    return hmac.compare_digest(signature, expected_sig)


def detect_provider_from_payload(payload: dict[str, Any] | str) -> str:
    """
    Attempt to detect provider (meta vs twilio) from payload structure.
    Returns 'meta' or 'twilio' based on payload structure.
    """
    if isinstance(payload, str):
        # Form-encoded = Twilio
        return "twilio"

    # Check for Meta-specific fields
    if "entry" in payload and isinstance(payload.get("entry"), list):
        return "meta"

    # Check for Twilio-specific fields
    if "MessageSid" in payload or "EventType" in payload:
        return "twilio"

    # Default to configured provider
    return settings.WHATSAPP_PROVIDER
