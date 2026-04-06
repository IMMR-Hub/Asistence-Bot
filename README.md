# Universal Sales Automation Core v1.0.0

Production-ready modular core for WhatsApp messaging and email response automation. Multi-tenant, config-driven, with LLM-powered classification and intelligent escalation.

**⚠️ Email Scope:** Email *outbound responses* are fully functional (SMTP). Email *inbound reception* requires external provider integration (Phase 2).

## Quick Start (Docker Compose)

### Prerequisites
- Docker Desktop: https://www.docker.com/products/docker-desktop
- Git (optional): https://git-scm.com/download

### Setup
```bash
cd C:\Users\Daniel\universal-sales-automation-core
copy .env.example .env
# Edit .env with your API_SECRET_KEY

docker compose up --build
```

### Verify
```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Create First Tenant

### PowerShell (Windows)
```powershell
$API_KEY = "your-api-secret-key"
$response = curl -X POST http://localhost:8000/api/tenants `
  -H "Content-Type: application/json" `
  -H "X-API-Key: $API_KEY" `
  -d '{"tenant_slug":"forestal-caaguazu","business_name":"Forestal","timezone":"America/Asuncion","default_language":"es"}' `
  | ConvertFrom-Json

$TENANT_ID = $response.id

curl -X POST "http://localhost:8000/api/tenants/$TENANT_ID/configs" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: $API_KEY" `
  -d '{"config":{"tenant_slug":"forestal-caaguazu","business_name":"Forestal","timezone":"America/Asuncion","default_language":"es","enabled_channels":["whatsapp","email"],"brand_tone":"professional","escalation_rules":{"confidence_threshold":0.72,"always_escalate_complaints":true}}}'
```

## Test the System
```bash
curl -X POST http://localhost:8000/api/test/process-message `
  -H "Content-Type: application/json" `
  -H "X-API-Key: your-api-secret-key" `
  -d '{"tenant_slug":"forestal-caaguazu","channel":"whatsapp","contact_phone":"595981234567","contact_name":"Juan","text_content":"Hola"}'
```

## API Endpoints
- GET /health - Health check
- GET /ready - Full check
- POST /api/tenants - Create tenant
- GET /api/tenants/{id} - Get tenant
- POST /api/tenants/{id}/configs - Configure
- POST /webhooks/whatsapp/inbound - WhatsApp inbound webhook
- POST /webhooks/email/inbound - Email inbound webhook (requires external adapter)
- POST /api/test/process-message - Test message

## Local Development (Without Docker)
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Project Structure
- app/main.py - FastAPI app
- app/db/ - Models + repositories
- app/modules/ - 8 business modules
- app/channels/ - WhatsApp + email adapters
- app/tests/ - Unit + integration tests

## Troubleshooting
```bash
docker compose logs api
docker compose logs worker
docker compose ps
curl http://localhost:8000/ready | jq .
```

## Modules Overview
- inbound_router - Normalize messages
- intent_classifier - LLM classification
- entity_extractor - Extract fields
- knowledge_resolver - Load FAQs
- response_orchestrator - Generate replies
- crm_writer - Persist data
- follow_up_engine - Schedule follow-ups
- human_escalation - Create escalations
- audit_logger - Log events
- whatsapp_adapter - WhatsApp integration
- email_adapter - Email integration

## Email Integration

### Outbound Email (✅ Functional)
The system can send email responses via SMTP. Configure in `.env`:
```
SMTP_HOST_OPTIONAL=smtp.gmail.com
SMTP_PORT_OPTIONAL=587
SMTP_USERNAME_OPTIONAL=your-email@gmail.com
SMTP_PASSWORD_OPTIONAL=your-app-password
SMTP_USE_TLS=true
```

When a customer inquiry arrives (via any channel), the system:
1. Classifies the intent
2. Generates a response
3. Sends response email via SMTP (if channel=email)

### Inbound Email (⏳ Phase 2 — Pending)
Email inbound reception requires integration with an email provider:

**Option A: Gmail API** (recommended for cloud)
- Listen to Gmail push notifications via Cloud Pub/Sub
- Convert to `EmailInboundPayload` schema
- POST to `/webhooks/email/inbound`

**Option B: Microsoft 365 / Outlook** (enterprise)
- Use Microsoft Graph API webhooks
- Same normalization to `EmailInboundPayload`

**Option C: Self-hosted IMAP** (on-premises)
- Run separate IMAP polling service
- Forward parsed emails to `/webhooks/email/inbound`

**Current State:** Webhook endpoint exists at `/webhooks/email/inbound` (POST), but no provider integration is implemented. External email adapter is required before inbound works.

## Docs
http://localhost:8000/docs (Swagger UI)

Built with FastAPI + PostgreSQL + Groq LLM API (OpenAI-compatible)
