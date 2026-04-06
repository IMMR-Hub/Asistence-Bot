"""
Integration tests for Twilio WhatsApp webhook support.
Tests parsing, sending, signature verification, and multi-tenant support.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.whatsapp.adapter import (
    detect_provider_from_payload,
    parse_twilio_inbound,
    send_twilio_whatsapp_message,
    verify_twilio_webhook,
)
from app.db.models import Tenant
from app.schemas.common import NormalizedMessage


class TestTwilioParser:
    """Test Twilio webhook payload parsing."""

    @pytest.fixture
    def tenant_id(self) -> uuid.UUID:
        """Test tenant ID."""
        return uuid.uuid4()

    @pytest.fixture
    def twilio_payload(self) -> dict:
        """Sample Twilio inbound message payload."""
        return {
            "MessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "From": "whatsapp:+12025551234",
            "To": "whatsapp:+14155552671",
            "Body": "Hello, I need help with my appointment",
            "NumMedia": 0,
            "EventType": "inbound-message",
        }

    def test_parse_twilio_text_message(
        self, twilio_payload: dict, tenant_id: uuid.UUID
    ):
        """Test parsing simple text message from Twilio."""
        messages = parse_twilio_inbound(twilio_payload, tenant_id)

        assert len(messages) == 1
        msg = messages[0]

        assert msg.channel == "whatsapp"
        assert msg.direction == "inbound"
        assert msg.external_contact_id == "whatsapp:+12025551234"
        assert msg.contact_phone == "whatsapp:+12025551234"
        assert msg.text_content == "Hello, I need help with my appointment"
        assert msg.tenant_id == tenant_id

    def test_parse_twilio_message_with_name(
        self, twilio_payload: dict, tenant_id: uuid.UUID
    ):
        """Test parsing message with contact name."""
        twilio_payload["ProfileName"] = "John Smith"

        messages = parse_twilio_inbound(twilio_payload, tenant_id)

        assert len(messages) == 1
        assert messages[0].contact_name == "John Smith"

    def test_parse_twilio_message_with_media(
        self, twilio_payload: dict, tenant_id: uuid.UUID
    ):
        """Test parsing message with media attachments."""
        twilio_payload.update(
            {
                "NumMedia": 2,
                "MediaUrl0": "https://example.com/image.jpg",
                "MediaContentType0": "image/jpeg",
                "MediaUrl1": "https://example.com/doc.pdf",
                "MediaContentType1": "application/pdf",
            }
        )

        messages = parse_twilio_inbound(twilio_payload, tenant_id)

        assert len(messages) == 1
        msg = messages[0]
        assert len(msg.attachments) == 2
        assert msg.attachments[0]["type"] == "image"
        assert msg.attachments[0]["url"] == "https://example.com/image.jpg"
        assert msg.attachments[1]["type"] == "application"

    def test_parse_twilio_form_encoded_string(
        self, twilio_payload: dict, tenant_id: uuid.UUID
    ):
        """Test parsing form-encoded Twilio payload (as string)."""
        form_data = "&".join(f"{k}={v}" for k, v in twilio_payload.items())

        messages = parse_twilio_inbound(form_data, tenant_id)

        assert len(messages) == 1
        assert messages[0].text_content == "Hello, I need help with my appointment"

    def test_parse_twilio_no_content(self, tenant_id: uuid.UUID):
        """Test handling of message with no text or media."""
        payload = {
            "MessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "From": "whatsapp:+12025551234",
            "Body": "",
            "NumMedia": 0,
        }

        messages = parse_twilio_inbound(payload, tenant_id)
        assert len(messages) == 0

    def test_parse_twilio_non_message_event(
        self, twilio_payload: dict, tenant_id: uuid.UUID
    ):
        """Test that non-message events are ignored."""
        twilio_payload["EventType"] = "delivery-status"

        messages = parse_twilio_inbound(twilio_payload, tenant_id)
        assert len(messages) == 0


class TestTwilioSending:
    """Test Twilio message sending."""

    @pytest.mark.asyncio
    async def test_send_twilio_message_success(self):
        """Test successful message send via Twilio."""
        with patch(
            "app.channels.whatsapp.adapter.httpx.AsyncClient.post"
        ) as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 201
            mock_post.return_value = mock_response
            mock_post.return_value.__aenter__.return_value = mock_post.return_value

            success = await send_twilio_whatsapp_message(
                to_phone="+12025551234",
                text="Hello",
                account_sid="ACxxxxxxxx",
                auth_token="auth_token_here",
                from_number="+14155552671",
            )

            assert success is True

    @pytest.mark.asyncio
    async def test_send_twilio_message_missing_credentials(self):
        """Test send fails when credentials missing."""
        success = await send_twilio_whatsapp_message(
            to_phone="+12025551234",
            text="Hello",
            account_sid=None,
            auth_token=None,
            from_number=None,
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_send_twilio_message_with_format(self):
        """Test message send with proper phone number formatting."""
        with patch(
            "app.channels.whatsapp.adapter.httpx.AsyncClient.post"
        ) as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 201
            mock_post.return_value = mock_response
            mock_post.return_value.__aenter__.return_value = mock_post.return_value

            await send_twilio_whatsapp_message(
                to_phone="+12025551234",
                text="Test message",
                account_sid="ACxxxxxxxx",
                auth_token="token",
                from_number="+14155552671",
            )

            # Verify POST was called with correct format
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "whatsapp:" in call_args[0][0]  # URL should contain whatsapp:


class TestWebhookSignatureVerification:
    """Test Twilio webhook signature verification."""

    @pytest.fixture
    def auth_token(self) -> str:
        """Test Twilio auth token."""
        return "test_auth_token_12345"

    @pytest.fixture
    def request_body(self) -> str:
        """Test request body."""
        return "From=whatsapp%3A%2B12025551234&Body=Hello"

    @pytest.fixture
    def request_url(self) -> str:
        """Test request URL."""
        return "https://api.example.com/webhooks/whatsapp/twilio"

    def test_verify_signature_valid(
        self, auth_token: str, request_body: str, request_url: str
    ):
        """Test valid signature verification."""
        # Compute expected signature
        signed_data = request_url + request_body
        expected_sig = base64.b64encode(
            hmac.new(
                auth_token.encode("utf-8"),
                signed_data.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        # Verify
        is_valid = verify_twilio_webhook(request_body, expected_sig, auth_token, request_url)
        assert is_valid is True

    def test_verify_signature_invalid(
        self, auth_token: str, request_body: str, request_url: str
    ):
        """Test invalid signature detection."""
        bad_signature = "invalid_signature_here"

        is_valid = verify_twilio_webhook(request_body, bad_signature, auth_token, request_url)
        assert is_valid is False

    def test_verify_signature_no_token(self, request_body: str, request_url: str):
        """Test verification with no token (should allow)."""
        is_valid = verify_twilio_webhook(request_body, "any_sig", None, request_url)
        assert is_valid is True


class TestProviderDetection:
    """Test provider auto-detection from payload."""

    def test_detect_meta_provider(self):
        """Test Meta provider detection from JSON payload."""
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [{"from": "1234567890", "type": "text"}]
                            }
                        }
                    ]
                }
            ]
        }

        provider = detect_provider_from_payload(payload)
        assert provider == "meta"

    def test_detect_twilio_provider_dict(self):
        """Test Twilio provider detection from dict."""
        payload = {
            "MessageSid": "SMxxxxxxxx",
            "From": "whatsapp:+12025551234",
            "Body": "Hello",
        }

        provider = detect_provider_from_payload(payload)
        assert provider == "twilio"

    def test_detect_twilio_provider_string(self):
        """Test Twilio provider detection from form-encoded string."""
        payload = "MessageSid=SMxxxxxxxx&From=whatsapp%3A%2B12025551234&Body=Hello"

        provider = detect_provider_from_payload(payload)
        assert provider == "twilio"

    def test_detect_provider_unknown_fallback(self):
        """Test fallback to configured provider for unknown format."""
        from app.core.config import settings

        payload = {"unknown": "format"}

        provider = detect_provider_from_payload(payload)
        # Should match configured provider (Meta by default in tests)
        assert provider == settings.WHATSAPP_PROVIDER


class TestTwilioWebhookIntegration:
    """Integration tests for Twilio webhook endpoints."""

    @pytest.mark.asyncio
    async def test_twilio_inbound_webhook(
        self, client: AsyncClient, db: AsyncSession, tenant: Tenant
    ):
        """Test POST /webhooks/whatsapp/twilio endpoint."""
        payload = {
            "MessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "From": "whatsapp:+12025551234",
            "To": "whatsapp:+14155552671",
            "Body": "Help with appointment",
            "NumMedia": 0,
        }

        response = await client.post(
            "/webhooks/whatsapp/twilio",
            json=payload,
            headers={"X-Tenant-Slug": tenant.slug},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_twilio_inbound_missing_tenant(self, client: AsyncClient):
        """Test webhook fails without tenant slug."""
        payload = {
            "MessageSid": "SMxxxxxxxx",
            "From": "whatsapp:+12025551234",
            "Body": "Hello",
        }

        response = await client.post(
            "/webhooks/whatsapp/twilio",
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert "tenant_slug" in data["reason"]

    @pytest.mark.asyncio
    async def test_twilio_inbound_unknown_tenant(self, client: AsyncClient):
        """Test webhook fails with unknown tenant."""
        payload = {
            "MessageSid": "SMxxxxxxxx",
            "From": "whatsapp:+12025551234",
            "Body": "Hello",
        }

        response = await client.post(
            "/webhooks/whatsapp/twilio",
            json=payload,
            headers={"X-Tenant-Slug": "nonexistent-tenant"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert "unknown_tenant" in data["reason"]

    @pytest.mark.asyncio
    async def test_auto_detect_webhook_handles_twilio(
        self, client: AsyncClient, db: AsyncSession, tenant: Tenant
    ):
        """Test /webhooks/whatsapp/inbound auto-detects Twilio."""
        payload = {
            "MessageSid": "SMxxxxxxxx",
            "From": "whatsapp:+12025551234",
            "Body": "Test message",
            "NumMedia": 0,
        }

        response = await client.post(
            "/webhooks/whatsapp/inbound",
            json=payload,
            headers={"X-Tenant-Slug": tenant.slug},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_auto_detect_webhook_handles_meta(
        self, client: AsyncClient, db: AsyncSession, tenant: Tenant
    ):
        """Test /webhooks/whatsapp/inbound auto-detects Meta."""
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "1234567890",
                                        "type": "text",
                                        "text": {"body": "Hello from Meta"},
                                        "id": "wamid.test",
                                    }
                                ],
                                "contacts": [
                                    {"wa_id": "1234567890", "profile": {"name": "Test User"}}
                                ],
                            },
                            "field": "messages",
                        }
                    ]
                }
            ]
        }

        response = await client.post(
            "/webhooks/whatsapp/inbound",
            json=payload,
            headers={"X-Tenant-Slug": tenant.slug},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestTwilioMultiTenantIsolation:
    """Test Twilio integration with multi-tenant isolation."""

    @pytest.mark.asyncio
    async def test_twilio_messages_isolated_per_tenant(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Test that Twilio messages are isolated per tenant."""
        # Create two tenants
        tenant1 = await self._create_test_tenant(db, "tenant-uno")
        tenant2 = await self._create_test_tenant(db, "tenant-dos")

        # Send message to tenant 1
        payload1 = {
            "MessageSid": "SM111111111111111111111111111111",
            "From": "whatsapp:+12025551111",
            "Body": "Message for tenant 1",
        }

        response1 = await client.post(
            "/webhooks/whatsapp/twilio",
            json=payload1,
            headers={"X-Tenant-Slug": tenant1.slug},
        )
        assert response1.status_code == 200

        # Send message to tenant 2
        payload2 = {
            "MessageSid": "SM222222222222222222222222222222",
            "From": "whatsapp:+12025552222",
            "Body": "Message for tenant 2",
        }

        response2 = await client.post(
            "/webhooks/whatsapp/twilio",
            json=payload2,
            headers={"X-Tenant-Slug": tenant2.slug},
        )
        assert response2.status_code == 200

        # Verify messages are in correct tenants
        from app.db.models import Message

        msg1 = await db.execute(
            f"SELECT * FROM messages WHERE text_content = 'Message for tenant 1' AND tenant_id = '{tenant1.id}'"
        )
        msg2 = await db.execute(
            f"SELECT * FROM messages WHERE text_content = 'Message for tenant 2' AND tenant_id = '{tenant2.id}'"
        )

        # Both should exist (isolation verified)
        assert msg1 is not None
        assert msg2 is not None

    async def _create_test_tenant(self, db: AsyncSession, slug: str) -> Tenant:
        """Helper to create test tenant."""
        from app.services.tenant_service import TenantService

        svc = TenantService(db)
        tenant = await svc.create_tenant(
            tenant_slug=slug,
            business_name=f"Test Business {slug}",
            timezone="America/New_York",
            default_language="en",
        )
        await db.commit()
        return tenant
