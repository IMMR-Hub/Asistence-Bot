from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.channels.whatsapp.adapter import parse_meta_inbound


SAMPLE_META_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "ENTRY_ID",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "PHONE_ID"},
                        "contacts": [
                            {"profile": {"name": "Juan Perez"}, "wa_id": "595981000001"}
                        ],
                        "messages": [
                            {
                                "from": "595981000001",
                                "id": "wamid.test123",
                                "timestamp": "1700000000",
                                "text": {"body": "Hola, ¿tienen madera disponible?"},
                                "type": "text",
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


def test_parse_meta_inbound_basic():
    tenant_id = uuid.uuid4()
    messages = parse_meta_inbound(SAMPLE_META_PAYLOAD, tenant_id)
    assert len(messages) == 1
    msg = messages[0]
    assert msg.channel == "whatsapp"
    assert msg.direction == "inbound"
    assert msg.contact_phone == "595981000001"
    assert msg.contact_name == "Juan Perez"
    assert msg.text_content == "Hola, ¿tienen madera disponible?"
    assert msg.message_id == "wamid.test123"
    assert msg.tenant_id == tenant_id


def test_parse_meta_inbound_empty_payload():
    msgs = parse_meta_inbound({"object": "test", "entry": []}, uuid.uuid4())
    assert msgs == []


def test_parse_meta_inbound_non_message_field():
    payload = {
        "object": "test",
        "entry": [
            {
                "changes": [
                    {"value": {}, "field": "statuses"}  # not 'messages'
                ]
            }
        ],
    }
    msgs = parse_meta_inbound(payload, uuid.uuid4())
    assert msgs == []


@pytest.mark.asyncio
async def test_whatsapp_webhook_endpoint(client, db_session, sample_tenant_config_dict):
    """Full webhook → lead creation flow."""
    from app.db.models.tenant import Tenant, TenantConfig
    from app.core.config import settings

    # Seed tenant
    tenant = Tenant(
        tenant_slug="wa-integration-test",
        business_name="WA Test",
        timezone="UTC",
        default_language="es",
    )
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)

    cfg = TenantConfig(
        tenant_id=tenant.id,
        config_json={**sample_tenant_config_dict, "tenant_slug": "wa-integration-test"},
        version=1,
        is_active=True,
    )
    db_session.add(cfg)
    await db_session.flush()

    mock_classification = json.dumps({
        "intent": "product_inquiry",
        "lead_temperature": "warm",
        "urgency": "medium",
        "confidence": 0.88,
        "summary": "Asking about wood availability",
        "entities": {"customer_name": "Juan Perez", "language": "es"},
    })
    mock_response = json.dumps({"response_text": "Hola Juan, sí tenemos disponibilidad."})

    with (
        patch("app.modules.intent_classifier.classifier.get_ollama_client") as mock_get_client,
        patch("app.channels.whatsapp.adapter.send_whatsapp_message", new=AsyncMock(return_value=True)),
    ):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=[mock_classification, mock_response])
        mock_get_client.return_value = mock_client

        resp = await client.post(
            "/webhooks/whatsapp/inbound",
            json=SAMPLE_META_PAYLOAD,
            headers={
                "X-Tenant-Slug": "wa-integration-test",
                "X-API-Key": settings.API_SECRET_KEY,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] == 1
    assert data["results"][0]["message_id"] is not None
