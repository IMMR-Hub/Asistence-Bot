from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.email.adapter import parse_email_inbound, send_email
from app.channels.whatsapp.adapter import (
    parse_meta_inbound,
    parse_twilio_inbound,
    send_whatsapp_message,
    verify_twilio_webhook,
    detect_provider_from_payload,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.webhook import EmailInboundPayload, TestProcessMessageRequest, WhatsAppInboundPayload
from app.services.message_processor import MessageProcessor
from app.services.tenant_service import TenantService

logger = get_logger(__name__)

router = APIRouter(tags=["webhooks"])


# ----- WhatsApp -----

@router.get("/webhooks/whatsapp/inbound")
async def whatsapp_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> Any:
    """Meta webhook verification handshake."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post("/webhooks/whatsapp/inbound", status_code=status.HTTP_200_OK)
async def whatsapp_inbound(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Receive WhatsApp inbound messages from Meta Cloud API or Twilio.
    Auto-detects provider from payload structure.
    Tenant is resolved from X-Tenant-Slug header or tenant_slug query parameter.
    """
    raw_body = await request.body()

    # Tenant resolution: check header first, then query parameter
    tenant_slug = request.headers.get("X-Tenant-Slug", "") or request.query_params.get("tenant_slug", "")
    if not tenant_slug:
        logger.warning("whatsapp_inbound_missing_tenant_slug")
        return {"status": "ignored", "reason": "missing_tenant_slug"}

    svc = TenantService(db)
    tenant = await svc.get_tenant_by_slug(tenant_slug)
    if not tenant:
        logger.warning("whatsapp_inbound_unknown_tenant", slug=tenant_slug)
        return {"status": "ignored", "reason": "unknown_tenant"}

    # Detect provider from payload
    try:
        payload_dict = await request.json()
    except (json.JSONDecodeError, ValueError):
        # If JSON parsing fails, it's Twilio form-encoded
        payload_dict = raw_body.decode("utf-8")

    provider = detect_provider_from_payload(payload_dict)
    logger.info("whatsapp_inbound_detected_provider", provider=provider, tenant=tenant_slug)

    # Parse based on provider
    if provider == "twilio":
        # Verify Twilio signature if configured (skip in development)
        if settings.APP_ENV == "production":
            x_twilio_sig = request.headers.get("X-Twilio-Signature", "")
            request_url = str(request.url)
            if x_twilio_sig and not verify_twilio_webhook(
                raw_body.decode("utf-8"), x_twilio_sig, url=request_url
            ):
                logger.warning("twilio_webhook_signature_verification_failed")
                return {"status": "error", "reason": "signature_verification_failed"}

        messages = parse_twilio_inbound(payload_dict, tenant.id)
    else:
        # Meta provider — payload_dict already parsed as JSON above
        messages = parse_meta_inbound(payload_dict, tenant.id)

    if not messages:
        return {"status": "ok", "processed": 0}

    async def _send_fn(
        tenant_id: uuid.UUID, contact: Any, channel: str, text: str
    ) -> bool:
        phone = contact.phone or contact.external_contact_id or ""
        return await send_whatsapp_message(
            to_phone=phone, text=text, provider=provider
        )

    processor = MessageProcessor(db)
    results = []
    for msg in messages:
        result = await processor.process(msg, send_fn=_send_fn)
        results.append(
            {
                "message_id": str(result.message_id),
                "escalated": result.escalated,
                "response_sent": result.response_sent,
            }
        )

    return {"status": "ok", "processed": len(results), "results": results}


@router.post("/webhooks/whatsapp/twilio", status_code=status.HTTP_200_OK)
async def whatsapp_twilio_inbound(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Dedicated Twilio WhatsApp webhook endpoint.
    Tenant is resolved from X-Tenant-Slug header or tenant_slug query parameter.
    """
    raw_body = await request.body()

    # Tenant resolution: check header first, then query parameter
    tenant_slug = request.headers.get("X-Tenant-Slug", "") or request.query_params.get("tenant_slug", "")
    if not tenant_slug:
        logger.warning("twilio_whatsapp_inbound_missing_tenant_slug")
        return {"status": "ignored", "reason": "missing_tenant_slug"}

    svc = TenantService(db)
    tenant = await svc.get_tenant_by_slug(tenant_slug)
    if not tenant:
        logger.warning("twilio_whatsapp_inbound_unknown_tenant", slug=tenant_slug)
        return {"status": "ignored", "reason": "unknown_tenant"}

    # Verify Twilio signature (skip in development)
    if settings.APP_ENV == "production":
        x_twilio_sig = request.headers.get("X-Twilio-Signature", "")
        request_url = str(request.url)
        if x_twilio_sig and not verify_twilio_webhook(
            raw_body.decode("utf-8"), x_twilio_sig, url=request_url
        ):
            logger.warning("twilio_webhook_signature_verification_failed", tenant=tenant_slug)
            return {"status": "error", "reason": "signature_verification_failed"}

    # Parse Twilio payload
    messages = parse_twilio_inbound(raw_body.decode("utf-8"), tenant.id)

    if not messages:
        return {"status": "ok", "processed": 0}

    async def _send_fn(
        tenant_id: uuid.UUID, contact: Any, channel: str, text: str
    ) -> bool:
        phone = contact.phone or contact.external_contact_id or ""
        return await send_whatsapp_message(to_phone=phone, text=text, provider="twilio")

    processor = MessageProcessor(db)
    results = []
    for msg in messages:
        result = await processor.process(msg, send_fn=_send_fn)
        results.append(
            {
                "message_id": str(result.message_id),
                "escalated": result.escalated,
                "response_sent": result.response_sent,
            }
        )

    return {"status": "ok", "processed": len(results), "results": results}


# ----- Email -----

@router.post("/webhooks/email/inbound", status_code=status.HTTP_200_OK)
async def email_inbound(
    payload: EmailInboundPayload,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive normalised email inbound payload."""
    svc = TenantService(db)
    tenant = await svc.get_tenant_by_slug(payload.tenant_slug)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{payload.tenant_slug}' not found",
        )

    msg = parse_email_inbound(payload, tenant.id)

    async def _send_fn(
        tenant_id: uuid.UUID, contact: Any, channel: str, text: str
    ) -> bool:
        email = contact.email or contact.external_contact_id or ""
        return await send_email(to_email=email, subject="Re: your inquiry", body=text)

    processor = MessageProcessor(db)
    result = await processor.process(msg, send_fn=_send_fn)

    return {
        "status": "ok",
        "message_id": str(result.message_id),
        "escalated": result.escalated,
        "response_sent": result.response_sent,
        "errors": result.errors,
    }


# ----- Internal test endpoint -----

@router.post("/api/test/process-message")
async def test_process_message(
    data: TestProcessMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Internal testing endpoint — not for production use."""
    svc = TenantService(db)
    tenant = await svc.get_tenant_by_slug(data.tenant_slug)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{data.tenant_slug}' not found",
        )

    from app.modules.inbound_router.router import InboundRouter
    from datetime import datetime, timezone

    router_module = InboundRouter()
    msg = router_module.build_from_raw(
        message_id=f"test-{uuid.uuid4()}",
        tenant_id=tenant.id,
        channel=data.channel,
        direction="inbound",
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
        text_content=data.text_content,
    )

    processor = MessageProcessor(db)
    result = await processor.process(msg, send_fn=None)

    return {
        "success": result.success,
        "message_id": str(result.message_id) if result.message_id else None,
        "lead_id": str(result.lead_id) if result.lead_id else None,
        "conversation_id": str(result.conversation_id) if result.conversation_id else None,
        "escalated": result.escalated,
        "escalation_reason": result.escalation_reason,
        "response_text": result.response_text,
        "errors": result.errors,
    }
