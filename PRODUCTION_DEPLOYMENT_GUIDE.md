# Production Deployment Guide

## Current Status ✅

- **State Machine**: Fully integrated and tested (10/10 tests passing)
- **Webhook**: Verified working at `/webhooks/whatsapp/inbound?tenant_slug={slug}`
- **Database Schema**: Migration (002) applied with ConversationMemory JSON storage
- **Architecture**: Pure state machine (Python logic → LLM text generation)
- **Ready**: First client deployment

---

## Phase 1: Pre-Deployment Checklist

### 1.1 Verify All Tests Pass Locally

```bash
cd C:\Users\Daniel\universal-sales-automation-core

# Run all unit tests
pytest app/tests/unit/test_orchestrator_state.py -v

# Expected: 10/10 passing
# ✓ test_urgent_without_identity_asks_for_data
# ✓ test_urgent_with_full_identity_escalates
# ✓ test_urgent_already_escalated_thanks_no_reply
# ✓ test_booking_asks_time_preference_once
# ✓ test_booking_offers_afternoon_slots_when_requested
# ✓ test_booking_slot_selection_does_not_re_ask_preference
# ✓ test_booking_does_not_confirm_without_real_confirmation
# ✓ test_booked_thanks_no_reply
# ✓ test_no_persona_restart_mid_conversation
# ✓ test_no_re_ask_name_if_already_captured
```

### 1.2 Docker Container Status

```bash
# Ensure all containers are running
docker-compose ps

# Expected output:
# salesbot_db      - Up (healthy)
# salesbot_redis   - Up (healthy)
# salesbot_ollama  - Up
# salesbot_api     - Up
# salesbot_worker  - Up (healthy)
```

### 1.3 API Health Check

```bash
# Test local endpoint
curl -X GET http://localhost:8000/api/health

# Expected: 200 OK with {"status": "ok"}
```

### 1.4 Webhook Integration Test

```bash
# Test message processing (with tenant_slug query parameter)
curl -X POST "http://localhost:8000/webhooks/whatsapp/inbound?tenant_slug=test" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp%3A%2B595987654321&Body=Me%20duele%20la%20muela&MessageSid=SM123"

# Expected: 200 OK
# {
#   "status": "ok",
#   "processed": 1,
#   "results": [
#     {
#       "message_id": "...",
#       "escalated": true,
#       "response_sent": true
#     }
#   ]
# }
```

---

## Phase 2: Production Deployment Steps

### 2.1 Choose Hosting Provider

#### Option A: DigitalOcean App Platform (Recommended - Easiest)

**Advantages:**
- One-click PostgreSQL + Redis provisioning
- Automatic HTTPS/SSL
- Auto-scaling
- $12-25/month starter

**Disadvantages:**
- Vendor lock-in
- Limited customization

#### Option B: DigitalOcean Droplets (Recommended - Most Control)

**Advantages:**
- Full control (install what you need)
- $6/month basic VPS
- Direct Docker Compose support
- Flexible scaling

**Disadvantages:**
- Manual setup required
- You manage updates/backups

#### Option C: AWS ECS/EKS (For Enterprise)

**Advantages:**
- Industry standard
- Managed Kubernetes
- Advanced monitoring

**Disadvantages:**
- $100+/month minimum
- Steep learning curve

### 2.2 Recommended Setup: DigitalOcean Droplets

#### Step 1: Create a Droplet

```bash
# 1. Login to DigitalOcean
# 2. Create new Droplet:
#    - Ubuntu 24.04 LTS
#    - 2GB RAM / 50GB SSD ($12/month) minimum
#    - New SSH key: "salesbot-prod"
#    - Region: Closest to your clients
# 3. Note the IP address (e.g., 192.0.2.1)
```

#### Step 2: SSH into the Droplet

```bash
# On your local machine
ssh -i "path/to/salesbot-prod" root@192.0.2.1

# Once logged in, run updates
apt update && apt upgrade -y
```

#### Step 3: Install Docker & Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install -y docker-compose

# Verify installation
docker --version
docker-compose --version
```

#### Step 4: Deploy the Application

```bash
# Clone repository into droplet
cd /opt
git clone https://github.com/YOUR_ORG/universal-sales-automation-core.git
cd universal-sales-automation-core

# Create production environment file
# ⚠️ CRITICAL: Change ALL placeholder values!
cp .env.production .env.prod

# Edit .env.prod with REAL credentials:
# nano .env.prod
#
# Replace:
# - DATABASE_URL → Real PostgreSQL URL (DigitalOcean Managed Database)
# - REDIS_URL → Real Redis URL
# - LLM_API_KEY → Your Groq API key
# - TWILIO_ACCOUNT_SID_OPTIONAL → Client's Twilio Account SID
# - TWILIO_AUTH_TOKEN_OPTIONAL → Client's Twilio Auth Token
# - TWILIO_WHATSAPP_NUMBER_OPTIONAL → Client's Twilio WhatsApp Number
# - API_SECRET_KEY → Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
# - WHATSAPP_VERIFY_TOKEN → Generate: python -c "import secrets; print(secrets.token_hex(16))"

# Pull and start containers with production .env
docker-compose --env-file .env.prod up -d

# Verify containers
docker-compose ps

# Check logs
docker-compose logs -f api
```

#### Step 5: Setup PostgreSQL Database (DigitalOcean Managed)

**Option A: Use DigitalOcean Managed Database**

```bash
# 1. Create managed PostgreSQL in DO console
# 2. Get connection string:
#    postgresql+asyncpg://user:pass@host:5432/db
# 3. Update DATABASE_URL in .env.prod
# 4. Run migrations:
docker-compose exec api alembic upgrade head
```

**Option B: Use Local PostgreSQL in Container**

```bash
# Database runs in docker-compose (already configured)
# Just ensure persistent volume: postgres_data
docker volume ls | grep postgres_data
```

#### Step 6: Setup Redis (DigitalOcean Managed or Container)

Similar to PostgreSQL, choose:
- DigitalOcean Managed Redis (easier, $15/month)
- Local Redis in container (free, less reliable)

#### Step 7: Configure Firewall

```bash
# Open ports 80 (HTTP) and 443 (HTTPS)
ufw allow 22   # SSH
ufw allow 80   # HTTP
ufw allow 443  # HTTPS
ufw enable
```

#### Step 8: Setup Nginx Reverse Proxy (Optional but Recommended)

```bash
# Install nginx
apt install -y nginx

# Create config
cat > /etc/nginx/sites-available/salesbot << 'EOF'
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /webhooks/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/salesbot /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

#### Step 9: Setup SSL Certificate (Let's Encrypt)

```bash
# Install certbot
apt install -y certbot python3-certbot-nginx

# Obtain certificate
certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Update nginx config to use HTTPS
certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renew
systemctl enable certbot.timer
```

---

## Phase 3: Twilio Configuration

### 3.1 Get Twilio Credentials

1. **Create Twilio Account**: https://www.twilio.com/console
2. **Get Account SID**: Dashboard → Account Info
3. **Get Auth Token**: Dashboard → Account Info
4. **Get WhatsApp Number**: https://www.twilio.com/console/sms/whatsapp/learn
5. **Note Twilio Phone Number**: e.g., `+1415-523-8886`

### 3.2 Register Webhook in Twilio Console

1. Go to: https://www.twilio.com/console/sms/whatsapp/sandbox/settings
2. **When a message comes in**:
   - Webhook URL: `https://yourdomain.com/webhooks/whatsapp/inbound?tenant_slug=YOUR_TENANT_SLUG`
   - Method: `POST`
3. **Status Callbacks**:
   - Webhook URL: `https://yourdomain.com/webhooks/whatsapp/status`
   - Method: `POST`
4. **Save**

### 3.3 Test Twilio Connection

```bash
# From your droplet
curl -X POST "https://yourdomain.com/webhooks/whatsapp/inbound?tenant_slug=test" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp%3A%2B595987654321&Body=Test%20message&MessageSid=SM123"

# Expected: 200 OK with processed: 1
```

---

## Phase 4: Database Initialization

### 4.1 Create Tenant

```bash
# SSH into droplet
ssh -i "path/to/key" root@192.0.2.1

# Access database
docker-compose exec db psql -U salesbot -d salesbot_db -c "
INSERT INTO tenants (id, slug, name, created_at, updated_at)
VALUES (
  gen_random_uuid(),
  'first-client',
  'First Dental Clinic',
  NOW(),
  NOW()
);"

# Verify
docker-compose exec db psql -U salesbot -d salesbot_db -c "SELECT id, slug, name FROM tenants;"
```

### 4.2 Initialize Tenant Configuration

```bash
# Use test endpoint to create initial config
curl -X POST "https://yourdomain.com/api/test/process-message" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "first-client",
    "channel": "whatsapp",
    "contact_name": "Test Contact",
    "contact_phone": "+595991234567",
    "text_content": "Hola, ¿cuál es tu horario?"
  }'

# Expected: 200 OK with successful message processing
```

---

## Phase 5: Client Handoff

### 5.1 Create Client Documentation

**Document to deliver to client:**

```markdown
# WhatsApp Bot Setup Guide for Clínica Demo

## Your Bot Details

- **Twilio Phone Number**: +1415-523-8886
- **Support Email**: your@email.com
- **Bot Name**: "Dental Assistant"
- **Available Hours**: Lunes-Viernes 8:00-18:00

## How It Works

1. **Patient sends message** → Bot receives via WhatsApp
2. **Bot asks questions** → Captures name, phone, symptoms
3. **Bot offers appointments** → Shows available time slots
4. **Patient books** → Confirmation sent
5. **Urgent cases** → Human staff notified immediately

## Test the Bot

Send a message to: **+1415-523-8886**

Example messages:
- "Me duele la muela" (bot escalates to doctor)
- "Quiero una cita" (bot asks for time preference)
- "Mañana a las 10" (bot shows available slots)

## Monitoring

- Dashboard: https://yourdomain.com/dashboard
- Escalated cases: https://yourdomain.com/escalations
- Analytics: https://yourdomain.com/analytics

## Support

Issues? Contact support@yourdomain.com
```

### 5.2 Client Credentials Handoff

Send to client (SECURELY):

```
Client: Clínica Demo
Tenant Slug: first-client
Twilio Number: +1415-523-8886
Dashboard URL: https://yourdomain.com
API Key: [generate and send securely]
```

---

## Phase 6: Monitoring & Maintenance

### 6.1 Health Checks

```bash
# Monitor containers
docker-compose ps

# Check recent logs
docker-compose logs --tail=50 api
docker-compose logs --tail=50 worker

# Database health
docker-compose exec db pg_isready
```

### 6.2 Automated Backups

```bash
# Backup PostgreSQL daily
0 2 * * * docker-compose exec -T db pg_dump -U salesbot salesbot_db | gzip > /backups/db_$(date +\%Y\%m\%d).sql.gz

# Upload to S3 or similar storage
# aws s3 sync /backups s3://your-backup-bucket/
```

### 6.3 Monitoring & Alerts

**Setup monitoring in DigitalOcean:**

1. Enable monitoring on droplet
2. Set alerts for:
   - CPU > 80%
   - Disk > 80%
   - Memory > 85%

**Application-level monitoring:**

- Check `/api/health` every 5 minutes
- Alert if response time > 2s
- Alert if any 5xx errors in logs

---

## Phase 7: Scaling & Future

### 7.1 When Traffic Grows

**If single droplet reaches capacity:**

1. **Vertical scaling**: Upgrade to 4GB RAM droplet
2. **Horizontal scaling**:
   - Deploy multiple API instances
   - Load balance with nginx
   - Shared PostgreSQL + Redis

### 7.2 Additional Features

- **Appointment reminders**: RQ scheduled jobs
- **Analytics dashboard**: Add reporting
- **Multi-language support**: Update state machine templates
- **Custom branding**: WhatsApp template messages

---

## Troubleshooting

### Problem: Webhook returns 404

**Solution:**
- Verify tenant_slug exists in database
- Check webhook URL includes query parameter: `?tenant_slug=YOUR_SLUG`
- Verify database connection

### Problem: LLM timeout (Twilio expects < 8s response)

**Solution:**
- Check Groq API key is valid
- Monitor LLM_TIMEOUT setting (should be 8s max)
- Enable Ollama fallback for redundancy

### Problem: Messages not being sent to Twilio

**Solution:**
- Verify TWILIO_ACCOUNT_SID and AUTH_TOKEN
- Check TWILIO_WHATSAPP_NUMBER matches registered number
- Verify Twilio webhook signature verification disabled in dev

### Problem: Database migration fails

**Solution:**
```bash
# Check migration status
docker-compose exec api alembic current

# List migrations
docker-compose exec api alembic history

# Rollback and retry
docker-compose exec api alembic downgrade -1
docker-compose exec api alembic upgrade head
```

---

## Success Criteria ✅

- [ ] All tests passing locally
- [ ] Production .env configured with real credentials
- [ ] Droplet provisioned with Docker
- [ ] PostgreSQL + Redis running
- [ ] Tenant created in database
- [ ] Webhook registered in Twilio console
- [ ] Test message processed successfully
- [ ] API returns 200 OK for health check
- [ ] Client can send message to WhatsApp number
- [ ] Bot responds appropriately
- [ ] Escalated cases appear in dashboard
- [ ] Backups running automatically

---

## Next Steps After Deploy

1. **Monitor first week**: Watch logs, escalations, response quality
2. **Gather feedback**: Ask client for improvement requests
3. **Tune templates**: Adjust conversation flows based on real usage
4. **Add features**: Appointment confirmations, reminders, etc.
5. **Scale up**: More clients, more complex workflows

---

## Questions?

**Support contacts:**
- Technical: [your email]
- Twilio account: [Twilio support contact]
- DigitalOcean: [DO support]

---

**Last Updated**: 2026-04-02
**State Machine Version**: v1.0 (10/10 tests)
**Tested With**: Python 3.11, PostgreSQL 16, Redis 7, Docker Compose 2.x
