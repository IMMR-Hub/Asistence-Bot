# Email Integration Guide

## Overview

The Universal Sales Automation Core supports email as a communication channel with a clear distinction between **outbound** (fully functional) and **inbound** (pending external integration).

---

## Current State

| Feature | Status | Notes |
|---------|--------|-------|
| **Outbound SMTP** | ✅ Functional | Sends email responses via configurable SMTP provider |
| **Inbound Email** | ⏳ Phase 2 | Webhook endpoint exists; requires external email adapter |
| **Email Storage** | ✅ Functional | All emails logged in PostgreSQL (messages table) |
| **Tenant Config** | ✅ Functional | Email can be enabled/disabled per tenant in `enabled_channels` |

---

## Email Outbound (SMTP)

### Configuration

Set in `.env` or docker-compose environment variables:

```bash
# Required for outbound to work
SMTP_HOST_OPTIONAL=smtp.gmail.com
SMTP_PORT_OPTIONAL=587
SMTP_USERNAME_OPTIONAL=your-email@gmail.com
SMTP_PASSWORD_OPTIONAL=your-app-password

# Optional
SMTP_USE_TLS=true  # Default: true (recommended)
```

### How It Works

1. **Message arrives** via webhook or test endpoint with `channel=email`
2. **System processes** (classify → generate response)
3. **Response sent** via `send_email()` function:
   - Constructs MIME message (RFC 5321/5322)
   - Connects to SMTP server
   - Authenticates with credentials
   - Sends message
   - Logs result

### Implementation Details

**File:** `app/channels/email/adapter.py`

```python
async def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_name: str | None = None,
    from_email: str | None = None,
) -> bool:
    """Send outbound email via SMTP (TLS)."""
```

**Features:**
- Timeout: 15 seconds per connection
- TLS support (required for Gmail, Office 365, etc.)
- Custom sender name/email per message
- Plain text emails (MIME type: text/plain, UTF-8)
- Error logging to structured logs

**Example Response:**
```
Customer: "What's the price of Product X?"
System Classification: pricing_request
System Response: "Thank you for your inquiry. Product X costs $49.99. Here's more info..."
Email Sent: from=support@company.com → to=customer@example.com
Status: ✅ Success
```

### Testing Outbound

Using the internal test endpoint:

```bash
curl -X POST http://localhost:8000/api/test/process-message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "tenant_slug": "vitaclinica",
    "channel": "email",
    "contact_email": "test@example.com",
    "contact_name": "John Doe",
    "text_content": "How much does a cleaning cost?"
  }'
```

Expected response:
```json
{
  "success": true,
  "response_sent": true,
  "response_text": "Thank you for your inquiry...",
  "errors": []
}
```

---

## Email Inbound (Phase 2 — External Integration)

### Architecture

The system provides a normalized webhook endpoint for receiving email. Your infrastructure must:

1. **Integrate with email provider** (Gmail, Outlook, etc.)
2. **Normalize incoming email** to `EmailInboundPayload` schema
3. **POST to `/webhooks/email/inbound`** on the core system

```
External Email Provider
       ↓
   Email Adapter Service (you build this)
       ↓
/webhooks/email/inbound (Universal Sales Automation Core)
       ↓
Internal Message Processing Pipeline
```

### Schema: `EmailInboundPayload`

**File:** `app/schemas/webhook.py`

```python
class EmailInboundPayload(BaseModel):
    tenant_slug: str                    # Required: maps to tenant
    from_email: str                     # Required: sender email
    from_name: str | None = None        # Optional: sender display name
    to_email: str                       # Required: recipient email
    subject: str | None = None          # Optional: email subject
    text_content: str | None = None     # Optional: plain text body
    html_content: str | None = None     # Optional: HTML body (will be stripped)
    message_id: str | None = None       # Optional: SMTP Message-ID header
    raw_headers: dict[str, str] = {}    # Optional: extra headers for audit
```

### Webhook Endpoint

**URL:** `POST /webhooks/email/inbound`

**Response:**
```json
{
  "status": "ok",
  "message_id": "email-12345678-...",
  "escalated": false,
  "response_sent": true,
  "errors": []
}
```

### Implementation Options

#### Option 1: Gmail API (Recommended for Cloud)

**Technology:** Google Cloud Pub/Sub + Cloud Functions

1. **Set up Gmail API Push:**
   - Enable Gmail API in Google Cloud Console
   - Create a service account
   - Grant `gmail.modify` scope

2. **Create Cloud Function (Python):**
   ```python
   import json
   import requests
   from google.cloud import pubsub_v1

   def handle_gmail_push(event, context):
       """Triggered by Pub/Sub message from Gmail push notification."""
       pubsub_message = base64.b64decode(event['data']).decode('utf-8')
       history_id = json.loads(pubsub_message)['historyId']

       # Fetch email from Gmail API
       service = build('gmail', 'v1', credentials=credentials)
       history = service.users().history().list(userId='me', startHistoryId=history_id).execute()

       for message_id in extract_message_ids(history):
           email_data = fetch_gmail_message(service, message_id)

           # Normalize to EmailInboundPayload
           payload = {
               "tenant_slug": "vitaclinica",
               "from_email": email_data['from'],
               "from_name": extract_name(email_data['from']),
               "to_email": email_data['to'],
               "subject": email_data['subject'],
               "text_content": email_data['body'],
               "message_id": email_data['message_id'],
           }

           # POST to webhook
           requests.post(
               'https://your-core.com/webhooks/email/inbound',
               json=payload,
               timeout=10
           )
   ```

3. **Cost:** ~$0 for most use cases (free tier includes Pub/Sub messages)

#### Option 2: Microsoft 365 / Outlook (Enterprise)

**Technology:** Microsoft Graph API webhooks

1. **Register Application:**
   - Azure Portal > App registrations
   - Grant `Mail.Read` delegated permission
   - Create client secret

2. **Subscribe to Mail Changes:**
   ```bash
   POST https://graph.microsoft.com/v1.0/subscriptions
   {
     "changeType": "created",
     "notificationUrl": "https://your-core.com/webhooks/email/inbound",
     "resource": "/me/mailFolders('Inbox')/messages",
     "expirationDateTime": "2026-03-31T00:00:00Z"
   }
   ```

3. **Handle Webhook Notifications:**
   - Verify subscription (Microsoft sends validation token)
   - Fetch full message via Graph API
   - Normalize and process as above

#### Option 3: Self-Hosted IMAP (On-Premises)

**Technology:** Separate Python service + IMAP

1. **Create IMAP Poller Service:**
   ```python
   import imaplib
   import email
   import requests
   from datetime import datetime, timedelta

   class IMAPPoller:
       def __init__(self, imap_host, username, password):
           self.host = imap_host
           self.username = username
           self.password = password

       def poll(self):
           """Check for new emails every 30 seconds."""
           with imaplib.IMAP4_SSL(self.host) as imap:
               imap.login(self.username, self.password)
               imap.select('INBOX')

               # Find emails from last 30 seconds
               status, message_nums = imap.search(None, 'RECENT')

               for msg_num in message_nums[0].split():
                   status, msg_data = imap.fetch(msg_num, '(RFC822)')
                   raw_email = msg_data[0][1]

                   msg = email.message_from_bytes(raw_email)

                   # Normalize and POST
                   payload = {
                       "tenant_slug": "vitaclinica",
                       "from_email": msg['From'],
                       "to_email": msg['To'],
                       "subject": msg['Subject'],
                       "text_content": extract_text(msg),
                       "message_id": msg['Message-ID'],
                   }

                   requests.post(
                       'http://localhost:8000/webhooks/email/inbound',
                       json=payload
                   )
   ```

2. **Deploy alongside Core:**
   - Add service in docker-compose.yml
   - Runs continuously, polls every 30 seconds
   - No external API dependency

3. **Cost:** Free (just compute resources)

---

## Configuration Per Tenant

### Enable Email Channel

```bash
curl -X POST http://localhost:8000/api/tenants/{tenant_id}/configs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "config": {
      "tenant_slug": "vitaclinica",
      "business_name": "Vita Clínica",
      "enabled_channels": ["whatsapp", "email"],
      "email_sender_name": "Vita Support",
      "email_sender_address": "support@vitaclinica.com"
    }
  }'
```

### Optional Fields

In `TenantConfigSchema`:
- `email_sender_name` - Display name for outbound emails
- `email_sender_address` - Sender email address (overrides SMTP_USERNAME_OPTIONAL)

---

## Monitoring & Troubleshooting

### Check Email Configuration

```bash
curl http://localhost:8000/ready | jq '.checks.smtp'
```

Expected output:
```json
{
  "smtp": {
    "configured": true,
    "host": "smtp.gmail.com",
    "port": 587
  }
}
```

### View Logs

```bash
docker compose logs api | grep email
docker compose logs api | grep smtp
```

### Test Outbound

```bash
# Simple test
curl -X POST http://localhost:8000/api/test/process-message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: api-key" \
  -d '{
    "tenant_slug": "vitaclinica",
    "channel": "email",
    "contact_email": "test@example.com",
    "text_content": "Hello"
  }'

# Check response_sent field
```

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| SMTP connection refused | SMTP_HOST_OPTIONAL not set or invalid | Verify SMTP credentials in `.env` |
| Authentication failed | Wrong username/password | Use app-specific password (Gmail), not account password |
| 587 port blocked | Firewall or ISP blocking | Use port 465 (SSL) instead, set SMTP_USE_TLS=false |
| Email not received | Spam folder | Mark as "not spam" in email client; check SPF/DKIM records |
| Inbound not working | No external adapter | Implement one of the 3 options above |

---

## Future Roadmap (Phase 2 / Phase 3)

1. **Inbound Email Support** (Phase 2)
   - Provide starter templates for Gmail/Outlook/IMAP adapters
   - Add email provider SDKs to requirements.txt

2. **Email Attachments** (Phase 3)
   - Parse attachments from inbound
   - Attach files to outbound responses
   - Virus scanning integration

3. **Email Threading** (Phase 3)
   - Track conversation threads (In-Reply-To headers)
   - Group related messages
   - Smart conversation context in LLM

4. **Advanced Email Features**
   - Template-based responses
   - HTML email rendering
   - Signature management per tenant
   - Send-time optimization (avoid spam filters)

---

## Reference

- **Webhook Adapter Code:** `app/channels/email/adapter.py`
- **Webhook Schema:** `app/schemas/webhook.py`
- **Endpoint:** `app/api/routes/webhooks.py` (lines 88-121)
- **Message Processor:** `app/services/message_processor.py`
- **Config:** `app/core/config.py` (SMTP_* settings)

---

**Last Updated:** 2026-03-31
**Status:** Email outbound functional, inbound pending Phase 2 integration
