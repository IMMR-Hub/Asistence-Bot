# Quick Reference - Production Deployment

## 🚀 30-Minute Deploy Checklist

### Before You Start
```bash
# Verify everything works locally
pytest app/tests/unit/test_orchestrator_state.py -v  # Should be 10/10
docker-compose up -d
curl http://localhost:8000/api/health              # Should be 200 OK
```

### Step 1: Provision Droplet (5 min)
```bash
# DigitalOcean Console
# → Create Ubuntu 24.04 Droplet
# → 2GB RAM, 50GB SSD
# → Get IP address (e.g., 192.0.2.1)
```

### Step 2: Install Docker (5 min)
```bash
ssh -i key.pem root@192.0.2.1

# Install Docker & Docker Compose
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose

# Verify
docker --version  # v25+
docker-compose --version  # v2+
```

### Step 3: Deploy App (10 min)
```bash
cd /opt
git clone [repo]
cd universal-sales-automation-core

# Copy and EDIT production config
cp .env.production .env.prod
nano .env.prod  # Replace ALL CAPS placeholders

# Deploy
docker-compose --env-file .env.prod up -d
docker-compose ps  # Verify all healthy

# Migrate database
docker-compose exec api alembic upgrade head
```

### Step 4: Setup Twilio Webhook (5 min)
```bash
# In Twilio Console:
# Webhook URL: https://yourdomain.com/webhooks/whatsapp/inbound?tenant_slug=CLIENT_SLUG
# Method: POST
# Save & Test
```

### Step 5: Test (5 min)
```bash
# Test endpoint
curl "https://yourdomain.com/webhooks/whatsapp/inbound?tenant_slug=test" \
  -d "From=whatsapp%3A%2B595987654321&Body=Test&MessageSid=SM123"

# Should return: {"status":"ok","processed":1,...}
```

---

## 📋 Environment Variables (Critical)

```bash
# MUST CHANGE FOR PRODUCTION
APP_ENV=production                          # ← Must be "production"
DATABASE_URL=postgresql+asyncpg://...      # ← Real DB URL
REDIS_URL=redis://...                      # ← Real Redis URL
LLM_API_KEY=gsk_...                         # ← Your Groq API key
API_SECRET_KEY=...                          # ← Generate: secrets.token_urlsafe(32)
WHATSAPP_VERIFY_TOKEN=...                  # ← Generate: secrets.token_hex(16)
TWILIO_ACCOUNT_SID_OPTIONAL=ACxx...         # ← Client's SID
TWILIO_AUTH_TOKEN_OPTIONAL=...              # ← Client's token
TWILIO_WHATSAPP_NUMBER_OPTIONAL=+1...       # ← Client's number
```

---

## 🔍 Testing Endpoints

### Health Check
```bash
curl https://yourdomain.com/api/health
# Expected: {"status":"ok"}
```

### Send Test Message
```bash
curl -X POST "https://yourdomain.com/webhooks/whatsapp/inbound?tenant_slug=test" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp%3A%2B595987654321&Body=Hola&MessageSid=SM123"

# Expected: {"status":"ok","processed":1,"results":[...]}
```

### Internal Test Endpoint
```bash
curl -X POST "https://yourdomain.com/api/test/process-message" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "test",
    "channel": "whatsapp",
    "contact_name": "Juan",
    "contact_phone": "+595991234567",
    "text_content": "Me duele la muela"
  }'

# Expected: {"success":true,"escalated":true,...}
```

---

## 🐳 Docker Commands

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs api --tail=50

# Database access
docker-compose exec db psql -U salesbot -d salesbot_db

# API shell
docker-compose exec api python

# Run tests
docker-compose exec api pytest app/tests/unit/test_orchestrator_state.py -v

# Restart service
docker-compose restart api

# Full restart
docker-compose down && docker-compose up -d
```

---

## 🗄️ Database Commands

```bash
# Connect to PostgreSQL
docker-compose exec db psql -U salesbot -d salesbot_db

# Create tenant
INSERT INTO tenants (slug, name) VALUES ('client-slug', 'Client Name');

# List tenants
SELECT id, slug, name FROM tenants;

# View conversation state
SELECT
  id, contact_id, state,
  conversation_state_payload->'state' as memory_state,
  awaiting_human_callback
FROM conversations
LIMIT 10;

# Escalated conversations
SELECT id, created_at, escalation_reason
FROM conversations
WHERE awaiting_human_callback = true
ORDER BY created_at DESC;

# Check migrations
SELECT version, description, success FROM alembic_version;
```

---

## 🐛 Common Issues & Fixes

### Problem: 404 Not Found on webhook
```
❌ curl: https://yourdomain.com/webhooks/twilio/message
✅ curl: https://yourdomain.com/webhooks/whatsapp/inbound?tenant_slug=test
```
**Fix**: Use correct endpoint path and add tenant_slug query parameter

### Problem: tenant_slug doesn't exist
```
Log: "whatsapp_inbound_unknown_tenant"
Fix: Create tenant in database first
```
**Fix**:
```bash
docker-compose exec db psql -U salesbot -d salesbot_db -c \
  "INSERT INTO tenants (slug, name) VALUES ('test', 'Test Tenant');"
```

### Problem: LLM timeout (> 8 seconds)
```
Error: TimeoutError from Groq API
Fix: Check Groq API key, check network latency
```
**Fix**:
```bash
# Verify Groq API key works
curl -H "Authorization: Bearer $LLM_API_KEY" \
  https://api.groq.com/openai/v1/models

# Check network latency
time curl https://api.groq.com/openai/v1/models
```

### Problem: Database migration fails
```
Fix: Check Alembic status, rollback if needed
```
**Fix**:
```bash
docker-compose exec api alembic current      # Check current version
docker-compose exec api alembic history      # View all versions
docker-compose exec api alembic upgrade head # Upgrade to latest
```

### Problem: Twilio webhook not receiving signatures
```
Log: "twilio_webhook_signature_verification_failed"
Fix: Skip signature verification in development (default)
```
**Fix**: Ensure `WEBHOOK_SIGNATURE_VERIFY=false` in development, or skip in code

---

## 📊 Monitoring Commands

```bash
# CPU & Memory
top
# or
htop  # Install: apt install -y htop

# Disk usage
df -h

# Network
netstat -tuln | grep 8000

# Docker stats
docker stats

# Recent logs (last 50 lines)
docker-compose logs --tail=50 api

# Follow logs in real-time
docker-compose logs -f api

# Count messages today
docker-compose exec db psql -U salesbot -d salesbot_db -c \
  "SELECT COUNT(*) FROM messages WHERE created_at > NOW() - INTERVAL '24 hours';"
```

---

## 🔐 Security Checklist

- [ ] Change `API_SECRET_KEY` to random 32+ char string
- [ ] Change `WHATSAPP_VERIFY_TOKEN` to random token
- [ ] Disable `DEBUG=false` in production
- [ ] Use strong database password
- [ ] Restrict database access to app only
- [ ] Enable firewall (ufw)
- [ ] Use HTTPS only (no HTTP)
- [ ] Rotate API keys quarterly
- [ ] Enable database backups
- [ ] Monitor logs for suspicious activity

---

## 📞 Support Escalation Path

**Level 1**: Check `/api/health` + logs
```bash
curl https://yourdomain.com/api/health
docker-compose logs -f api
```

**Level 2**: Database validation
```bash
docker-compose exec db pg_isready
# Check migrations: alembic current
```

**Level 3**: LLM provider status
```bash
# Check Groq API
curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $KEY"

# Or fallback to Ollama
curl http://ollama-server:11434/api/tags
```

**Level 4**: Twilio API status
```bash
# Check Twilio credentials
curl -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN \
  https://api.twilio.com/2010-04-01/Accounts.json
```

---

## 🚨 Emergency Response

### Database Down
```bash
# Restart database container
docker-compose restart db
docker-compose exec db pg_isready

# If persistent data loss, restore from backup
# aws s3 cp s3://backups/db_YYYYMMDD.sql.gz .
# docker-compose exec db psql < db_YYYYMMDD.sql
```

### API Crash Loop
```bash
# Check logs
docker-compose logs api | head -100

# Restart
docker-compose restart api

# Full reset (careful!)
docker-compose down
docker-compose up -d
docker-compose exec api alembic upgrade head
```

### Out of Disk Space
```bash
# Find large files
du -sh /* | sort -h

# Clean Docker images
docker image prune -a

# Clean logs (if needed)
find /var/lib/docker -name "*.log" -delete
```

---

## 📝 Useful Files

| File | Purpose |
|------|---------|
| `.env.prod` | Production configuration |
| `PRODUCTION_DEPLOYMENT_GUIDE.md` | Detailed deployment steps |
| `CLIENT_ONBOARDING_CHECKLIST.md` | Client setup checklist |
| `app/tests/unit/test_orchestrator_state.py` | Validation tests (run before deploy) |
| `alembic/versions/002_*.py` | Database schema migration |
| `docker-compose.yml` | Container definitions |

---

## 📚 Architecture Overview

```
WhatsApp Message
       ↓
Twilio API
       ↓
[API /webhooks/whatsapp/inbound] ← tenant_slug from query param
       ↓
[Message Parser] ← Detects Twilio format
       ↓
[Message Processor] ← Creates conversation if new
       ↓
[Response Orchestrator] ← STATE MACHINE
       ├─ Load ConversationMemory from DB
       ├─ Analyze intent + user message
       ├─ Decide next state
       ├─ Call LLM (Groq) to generate response
       └─ Save memory to DB
       ↓
[Send WhatsApp Response] ← Via Twilio
       ↓
Customer sees message ✅
```

---

## 🎯 Success Indicators

✅ **Deploy Successful When:**
- API responds with 200 OK
- Database migrations completed
- Test message returns `"status":"ok"`
- Response time < 2 seconds
- No error logs in first 10 requests
- Twilio webhook test passes

---

**Version**: 1.0
**Last Updated**: 2026-04-02
**Keep in Terminal**: YES - Reference during deploy
