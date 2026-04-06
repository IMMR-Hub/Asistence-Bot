# Twilio WhatsApp Sandbox Integration — Task 9/9

**Date:** 2026-03-31
**Status:** IMPLEMENTATION COMPLETE
**Version:** 1.0

---

## Overview

This document covers the integration of **Twilio WhatsApp Sandbox** as an alternative to Meta WhatsApp Cloud API for testing and production use.

### Why Twilio?

| Feature | Meta Sandbox | Twilio Sandbox | Status |
|---------|--------------|----------------|--------|
| **Setup Difficulty** | Complex (Meta Business Account) | Simple (Twilio account) | ✅ Twilio easier |
| **Testing Speed** | 24h approval | Immediate | ✅ Twilio faster |
| **Free Tier** | Limited ($0.003/msg) | Free tier available | ✅ Comparable |
| **No Business Account** | Required | Not required | ✅ Twilio better |
| **Production Grade** | Yes | Yes | ✅ Both production-ready |

**System Status:** Both Meta and Twilio supported simultaneously via `WHATSAPP_PROVIDER` configuration.

---

## Quick Start (5 minutes)

### 1. Create Twilio Account

```bash
# Visit https://www.twilio.com/console
# Sign up (free account includes $15 credit)
# Verify phone number
```

### 2. Enable WhatsApp Sandbox

```
Twilio Console → Messaging → WhatsApp Sandbox
```

**Sandbox Details:**
```
Account SID:    ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Auth Token:     YourAuthTokenHere
Sandbox Number: +1 415-XXX-XXXX (Twilio-provided)
```

### 3. Update Configuration

**Option A: Environment Variables (Recommended)**

```bash
# .env or docker-compose.yml
WHATSAPP_PROVIDER=twilio
TWILIO_ACCOUNT_SID_OPTIONAL=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN_OPTIONAL=YourAuthTokenHere
TWILIO_WHATSAPP_NUMBER_OPTIONAL=+14155552671
```

**Option B: Docker Compose**

```yaml
# docker-compose.yml
api:
  environment:
    WHATSAPP_PROVIDER: twilio
    TWILIO_ACCOUNT_SID_OPTIONAL: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    TWILIO_AUTH_TOKEN_OPTIONAL: YourAuthTokenHere
    TWILIO_WHATSAPP_NUMBER_OPTIONAL: +14155552671
```

### 4. Restart Services

```bash
# If environment changed, recreate container (not just restart)
docker compose down api
docker compose up -d api

# Verify
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"universal-sales-automation-core"}
```

### 5. Configure Webhook

**Twilio Console → Messaging → WhatsApp Sandbox → Webhook URL**

```
Inbound URL: http://your-domain.com/webhooks/whatsapp/twilio
Method: POST
```

**For Local Testing (ngrok):**

```bash
# Install ngrok: https://ngrok.com
ngrok http 8000

# Update Twilio webhook:
# Inbound URL: https://your-ngrok-id.ngrok.io/webhooks/whatsapp/twilio
```

### 6. Send Test Message

From your phone, send a WhatsApp message to the Twilio Sandbox number:

```
Message to +1 415-XXX-XXXX:
"join <sandbox-code>"

Expected response:
"Hello from Universal Sales Automation Core"
```

---

## Architecture

### Multi-Provider Support

The system now supports both Meta and Twilio with automatic detection:

```python
# Routes
POST /webhooks/whatsapp/inbound          # Auto-detects Meta or Twilio
POST /webhooks/whatsapp/twilio           # Explicit Twilio endpoint (recommended)
GET  /webhooks/whatsapp/inbound          # Meta verification (unchanged)
```

### Provider Detection

```python
# Automatic detection from payload structure
payload → detect_provider_from_payload()
  ├─ form-encoded (Twilio)
  ├─ JSON with "entry" field (Meta)
  └─ Falls back to WHATSAPP_PROVIDER setting
```

### Message Flow

**Inbound:**
```
Twilio Webhook
    ↓
POST /webhooks/whatsapp/twilio
    ↓
parse_twilio_inbound() — Converts form-encoded to NormalizedMessage
    ↓
MessageProcessor.process()
    ↓
Response sent via send_whatsapp_message(provider="twilio")
    ↓
send_twilio_whatsapp_message() — Twilio REST API
```

**Outbound:**
```
MessageProcessor → send_whatsapp_message()
    ↓
Dispatches based on provider setting
    ├─ Twilio: send_twilio_whatsapp_message()
    └─ Meta: send_meta_whatsapp_message()
    ↓
HTTP POST to respective API
```

---

## Configuration Reference

### Twilio Settings (app/core/config.py)

```python
WHATSAPP_PROVIDER: Literal["meta", "twilio"] = "meta"  # Set to "twilio"

# Twilio optional credentials
TWILIO_ACCOUNT_SID_OPTIONAL: str | None = None
TWILIO_AUTH_TOKEN_OPTIONAL: str | None = None
TWILIO_WHATSAPP_NUMBER_OPTIONAL: str | None = None
```

### Environment Variables

```bash
# Required for Twilio
WHATSAPP_PROVIDER=twilio
TWILIO_ACCOUNT_SID_OPTIONAL=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN_OPTIONAL=YourAuthTokenHere
TWILIO_WHATSAPP_NUMBER_OPTIONAL=+14155552671

# Optional (backward compatible)
WHATSAPP_VERIFY_TOKEN=testing123  # Still used for Meta
WHATSAPP_ACCESS_TOKEN=            # Can be empty if Twilio
WHATSAPP_PHONE_NUMBER_ID=         # Can be empty if Twilio
```

---

## API Reference

### Webhook Endpoints

#### POST /webhooks/whatsapp/inbound (Meta or Twilio)

```bash
curl -X POST http://localhost:8000/webhooks/whatsapp/inbound \
  -H "X-Tenant-Slug: vitaclinica" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp%3A%2B12025551234&Body=Hello&MessageSid=SM123456"

# Auto-detects provider and processes
```

#### POST /webhooks/whatsapp/twilio (Twilio only - Recommended)

```bash
# Explicit Twilio endpoint with signature verification
curl -X POST http://localhost:8000/webhooks/whatsapp/twilio \
  -H "X-Tenant-Slug: vitaclinica" \
  -H "X-Twilio-Signature: signature_hash" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp%3A%2B12025551234&Body=Hello&MessageSid=SM123456"
```

---

## Implementation Details

### New Functions

#### parse_twilio_inbound()

Converts Twilio form-encoded webhook payload to NormalizedMessage list.

```python
from app.channels.whatsapp.adapter import parse_twilio_inbound

messages = parse_twilio_inbound(payload_dict_or_string, tenant_id)
# Returns: list[NormalizedMessage]
```

**Payload Format:**
```
From: whatsapp:+1234567890
To: whatsapp:+14155552671
Body: Hello
MessageSid: SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NumMedia: 0
```

#### send_twilio_whatsapp_message()

Sends outbound message via Twilio API.

```python
from app.channels.whatsapp.adapter import send_twilio_whatsapp_message

success = await send_twilio_whatsapp_message(
    to_phone="+1234567890",
    text="Hello from bot",
    account_sid="ACxxxxxxxx",
    auth_token="token",
    from_number="+14155552671"
)
```

#### verify_twilio_webhook()

Verifies Twilio webhook signature (HMAC-SHA1).

```python
from app.channels.whatsapp.adapter import verify_twilio_webhook

is_valid = verify_twilio_webhook(
    request_body="From=...&Body=...",
    signature="signature_from_header",
    url="https://api.example.com/webhooks/whatsapp/twilio"
)
```

#### detect_provider_from_payload()

Auto-detects provider from payload structure.

```python
from app.channels.whatsapp.adapter import detect_provider_from_payload

provider = detect_provider_from_payload(payload_dict)
# Returns: "meta" or "twilio"
```

#### send_whatsapp_message() - Dispatcher

Routes to correct provider based on configuration.

```python
from app.channels.whatsapp.adapter import send_whatsapp_message

# Auto-routes based on settings.WHATSAPP_PROVIDER
success = await send_whatsapp_message(
    to_phone="+1234567890",
    text="Hello",
    provider="twilio"  # Override default
)
```

---

## Testing

### Unit Tests

```bash
# Run Twilio-specific tests
pytest app/tests/integration/test_twilio_webhook.py -v

# Run all WhatsApp tests (Meta + Twilio)
pytest app/tests/ -k "whatsapp" -v
```

### Test Message

**Send from your phone:**

```
WhatsApp message to Twilio Sandbox number:
→ "join unique-sandbox-code"
→ "Hello, I need help with my appointment"
```

**Expected Response:**

```
← "Hola, gracias por contactar. ¿En qué puedo ayudarte?"
  (Response in tenant's configured language)
```

**Verify in Database:**

```bash
# Check message was recorded
docker compose exec db psql -U salesbot -d salesbot_db << 'EOF'
SELECT m.text_content, m.channel, l.contact_name
FROM messages m
JOIN leads l ON m.lead_id = l.id
WHERE m.channel = 'whatsapp'
ORDER BY m.created_at DESC
LIMIT 5;
EOF
```

### Multi-Tenant Test

```bash
# Test with second tenant
curl -X POST http://localhost:8000/webhooks/whatsapp/twilio \
  -H "X-Tenant-Slug: testclinic" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp%3A%2B12025551234&Body=Help&MessageSid=SM999999"

# Verify response in English (testclinic language)
```

---

## Webhook Signature Verification

Twilio signs all webhook requests with HMAC-SHA1.

### How It Works

1. Twilio combines: `URL + RequestBody`
2. Hashes with SHA1 using your Auth Token
3. Sends Base64-encoded hash in `X-Twilio-Signature` header
4. System verifies signature matches

### Enabling Verification

```python
# Automatic if X-Twilio-Signature header present and auth token configured
# Already implemented in parse_twilio_inbound()

# Manual verification:
from app.channels.whatsapp.adapter import verify_twilio_webhook

is_valid = verify_twilio_webhook(
    request_body="From=...&Body=...",
    signature=request.headers["X-Twilio-Signature"],
    url=str(request.url)
)

if not is_valid:
    return {"error": "Invalid signature"}
```

---

## Troubleshooting

### Issue 1: "401 Unauthorized"

**Symptom:** Message send fails with 401 status

**Causes:**
- Invalid Account SID
- Invalid Auth Token
- Credentials not set in environment

**Solution:**

```bash
# Verify credentials
echo $TWILIO_ACCOUNT_SID_OPTIONAL
echo $TWILIO_AUTH_TOKEN_OPTIONAL

# Check Twilio Console for correct values
# Recreate container if changed
docker compose down api
docker compose up -d api
```

### Issue 2: "Webhook not triggering"

**Symptom:** Messages sent but no inbound webhook

**Causes:**
- Webhook URL not configured in Twilio Console
- Webhook URL unreachable (firewall, ngrok down)
- X-Tenant-Slug header missing
- Signature verification failed

**Solution:**

```bash
# Check Twilio logs
Twilio Console → Logs → Debugging

# Test webhook locally with ngrok
ngrok http 8000
# Update webhook URL in Twilio Console

# Check headers in request
docker compose logs api | grep "X-Tenant-Slug\|signature"
```

### Issue 3: "Provider detection failing"

**Symptom:** Payload sent but treated as wrong provider

**Causes:**
- Payload structure unexpected
- Mixed providers in requests

**Solution:**

```bash
# Use explicit endpoint
POST /webhooks/whatsapp/twilio  # For Twilio

# Check logs
docker compose logs api | grep "detect.*provider"

# Verify payload format in logs
docker compose logs api | grep "EventType\|MessageSid"
```

### Issue 4: "Multiple providers enabled causing conflicts"

**Symptom:** Sometimes message via Meta, sometimes via Twilio

**Solution:**

```python
# Be explicit in configuration
WHATSAPP_PROVIDER=twilio  # Set to ONE provider

# Or use explicit endpoints
/webhooks/whatsapp/inbound      # Uses auto-detection (slower)
/webhooks/whatsapp/twilio       # Explicit Twilio (recommended)
```

---

## Production Deployment

### Pre-Production Checklist

- [ ] Twilio account created and verified
- [ ] WhatsApp Sandbox enabled
- [ ] Environment variables configured
- [ ] Webhook URL set in Twilio Console
- [ ] Signature verification enabled
- [ ] Test message sends and receives correctly
- [ ] Multi-tenant isolation verified
- [ ] Logs show "provider=twilio" for inbound messages
- [ ] Response time <5s for message processing

### Migration from Meta to Twilio

```bash
# 1. Update environment variables
WHATSAPP_PROVIDER=twilio
TWILIO_ACCOUNT_SID_OPTIONAL=ACxxxxxxxx
TWILIO_AUTH_TOKEN_OPTIONAL=token
TWILIO_WHATSAPP_NUMBER_OPTIONAL=+1415...

# 2. Recreate container (not just restart)
docker compose down api
docker compose up -d api

# 3. Update webhook URL in Twilio Console
https://your-domain.com/webhooks/whatsapp/twilio

# 4. Test inbound/outbound
# Send message from phone → Check response
# Verify database records created

# 5. Monitor logs
docker compose logs -f api | grep "whatsapp\|twilio"

# 6. Rollback if needed
WHATSAPP_PROVIDER=meta
docker compose down api && docker compose up -d api
```

### Scaling Considerations

- Twilio handles similar throughput as Meta (100s msg/min per account)
- Use X-Tenant-Slug for multi-tenant routing
- No provider-specific scaling needed (same infrastructure)

---

## Differences: Meta vs Twilio

| Aspect | Meta | Twilio |
|--------|------|--------|
| **Payload Format** | JSON | Form-encoded |
| **Phone Prefix** | `+country_code_number` | `whatsapp:+country_code_number` |
| **Webhook Verification** | Query parameters (`hub.challenge`) | Header signature (HMAC-SHA1) |
| **Media Handling** | Media object in JSON | Media URL in separate fields |
| **Rate Limiting** | 80 msg/sec per business account | Depends on Twilio plan |
| **Webhook Retry** | Yes (24h window) | Yes (with exponential backoff) |
| **Testing Setup** | Meta Business Account required | Free Twilio account sufficient |

---

## FAQ

**Q: Can I use both Meta and Twilio simultaneously?**

A: Yes, but set `WHATSAPP_PROVIDER` to one. You can switch by updating config and restarting. System supports both API formats.

**Q: Do I need a Twilio paid account?**

A: No, free sandbox sufficient for development/testing. Production requires paid account.

**Q: How do I handle receiving messages from both providers?**

A: Configure separate webhooks:
- Meta: `/webhooks/whatsapp/inbound`
- Twilio: `/webhooks/whatsapp/twilio`

Or use auto-detection with `/webhooks/whatsapp/inbound` (routes both).

**Q: Is signature verification required?**

A: Recommended for security, but optional. System skips if no auth token configured.

**Q: How do I migrate a live customer from Meta to Twilio?**

A: Update config, update webhook URL in provider console, test thoroughly, monitor logs.

---

## Security Notes

1. **Auth Token**: Never commit to git. Use environment variables.
2. **Signature Verification**: Always enabled in production.
3. **Rate Limiting**: Implement at load balancer level for both providers.
4. **Webhook URL**: Must be HTTPS in production (HTTP allowed for ngrok/localhost).

---

## Summary

✅ **Twilio Integration Complete**

- [x] Twilio webhook parsing (form-encoded)
- [x] Twilio message sending (REST API)
- [x] Webhook signature verification (HMAC-SHA1)
- [x] Multi-tenant support
- [x] Provider auto-detection
- [x] Configuration options
- [x] Testing procedures
- [x] Documentation

**Next Steps:**
- Configure Twilio account
- Set environment variables
- Test webhook integration
- Monitor logs for successful message processing

---

**Generated:** 2026-03-31
**Status:** COMPLETE — Ready for production use
