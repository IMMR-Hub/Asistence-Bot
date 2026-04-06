from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.channels.email.adapter import parse_email_inbound
from app.core.config import settings
from app.schemas.webhook import EmailInboundPayload


def _make_email_payload(tenant_slug: str = "email-test") -> EmailInboundPayload:
    return EmailInboundPayload(
        tenant_slug=tenant_slug,
        from_email="cliente@example.com",
        from_name="Maria García",
        to_email="ventas@empresa.com",
        subject="Consulta sobre precios",
        text_content="Hola, quisiera saber los precios de sus productos.",
        message_id="<msg-001@example.com>",
    )


def test_parse_email_inbound_basic():
    tenant_id = uuid.uuid4()
    payload = _make_email_payload()
    msg = parse_email_inbound(payload, tenant_id)

    assert msg.channel == "email"
    assert msg.direction == "inbound"
    assert msg.contact_email == "cliente@example.com"
    assert msg.contact_name == "Maria García"
    assert "precios" in msg.text_content
    assert msg.tenant_id == tenant_id


def test_parse_email_html_fallback():
    tenant_id = uuid.uuid4()
    payload = EmailInboundPayload(
        tenant_slug="test",
        from_email="x@x.com",
        to_email="y@y.com",
        html_content="<p>Hola <b>mundo</b></p>",
        text_content=None,
    )
    msg = parse_email_inbound(payload, tenant_id)
    assert "Hola" in msg.text_content
    assert "<p>" not in msg.text_content  # HTML stripped


@pytest.mark.asyncio
async def test_email_inbound_endpoint(client, db_session, sample_tenant_config_dict):
    from app.db.models.tenant import Tenant, TenantConfig

    tenant = Tenant(
        tenant_slug="email-test",
        business_name="Email Test",
        timezone="UTC",
        default_language="es",
    )
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)

    cfg = TenantConfig(
        tenant_id=tenant.id,
        config_json={**sample_tenant_config_dict, "tenant_slug": "email-test"},
        version=1,
        is_active=True,
    )
    db_session.add(cfg)
    await db_session.flush()

    mock_classification = json.dumps({
        "intent": "pricing_request",
        "lead_temperature": "warm",
        "urgency": "medium",
        "confidence": 0.84,
        "summary": "Asking about prices",
        "entities": {"customer_name": "Maria García", "language": "es"},
    })
    mock_response = json.dumps({"response_text": "Hola Maria, con gusto te enviamos los precios."})

    with (
        patch("app.modules.intent_classifier.classifier.get_ollama_client") as mock_get_client,
        patch("app.channels.email.adapter.send_email", new=AsyncMock(return_value=True)),
    ):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=[mock_classification, mock_response])
        mock_get_client.return_value = mock_client

        resp = await client.post(
            "/webhooks/email/inbound",
            json=_make_email_payload("email-test").model_dump(),
            headers={"X-API-Key": settings.API_SECRET_KEY},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["message_id"] is not None
    assert data["escalated"] is False
