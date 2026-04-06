# Operations Runbook — Universal Sales Automation Core v1.0.0

**Effective Date:** 2026-03-31
**Version:** 1.0
**Audience:** DevOps, SRE, System Administrators
**Status:** PRODUCTION

---

## Table of Contents

1. [Deployment Procedures](#deployment-procedures)
2. [Health Monitoring](#health-monitoring)
3. [Troubleshooting Guide](#troubleshooting-guide)
4. [Scaling & Performance](#scaling--performance)
5. [Backup & Recovery](#backup--recovery)
6. [Maintenance Schedule](#maintenance-schedule)
7. [Log Analysis](#log-analysis)
8. [Security Procedures](#security-procedures)

---

## Deployment Procedures

### Initial Deployment (Fresh Environment)

#### Prerequisites
```bash
# Verify prerequisites
- Docker Desktop: Version 4.0+ installed
- Git: Latest version
- .env file: Configured with required variables
- API Key: Groq LLM API key obtained
```

#### Deployment Steps

**Step 1: Clone and Setup**
```bash
git clone <repo-url>
cd universal-sales-automation-core
cp .env.example .env
# Edit .env with production values
```

**Step 2: Build Images**
```bash
docker compose build --no-cache
```

**Expected:** ~2-3 minutes (builds API and worker images)

**Step 3: Start Services**
```bash
docker compose up -d
```

**Expected:** All 5 services start in order (db → redis → ollama → api, worker)

**Step 4: Run Migrations**
```bash
docker compose exec api alembic upgrade head
```

**Expected:** Alembic applies all pending migrations

**Step 5: Verify Health**
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"universal-sales-automation-core"}
```

**Step 6: Verify Ready**
```bash
curl http://localhost:8000/ready
# Expected: {"status":"ready","checks":{"db":"ok","redis":"ok","ollama":"ok"}}
```

**Step 7: Create First Tenant**
```bash
curl -X POST http://localhost:8000/api/tenants \
  -H "X-API-Key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "first-client",
    "business_name": "First Client Name",
    "timezone": "America/New_York",
    "default_language": "en"
  }'
```

**Status:** ✅ Deployment complete

---

### Upgrade Deployment (Existing Environment)

#### Pre-Upgrade Checklist
- [ ] Backup database: `docker compose exec db pg_dump -U salesbot salesbot_db > backup.sql`
- [ ] No active inbound messages being processed
- [ ] All follow-up jobs completed
- [ ] Notify team of maintenance window

#### Upgrade Steps
```bash
# 1. Pull latest code
git pull origin main

# 2. Rebuild images
docker compose build --no-cache api worker

# 3. Stop services (graceful shutdown)
docker compose down

# 4. Run migrations (safety check)
docker compose up -d db redis
sleep 5
docker compose exec db psql -U salesbot -d salesbot_db -c "SELECT COUNT(*) FROM tenants;"

# 5. Start all services
docker compose up -d

# 6. Verify health
sleep 10
curl http://localhost:8000/ready
```

#### Rollback Procedure (if needed)
```bash
# 1. Stop services
docker compose down

# 2. Restore database from backup
docker compose up -d db
docker compose exec db psql -U salesbot -d salesbot_db < backup.sql

# 3. Checkout previous version
git checkout <previous-commit>

# 4. Rebuild and restart
docker compose build --no-cache
docker compose up -d
```

---

## Health Monitoring

### Daily Health Checks

#### API Health Check
```bash
curl -s http://localhost:8000/health | jq '.status'
# Expected: "ok"
```

#### Dependency Health Check
```bash
curl -s http://localhost:8000/ready | jq '.checks'
# Expected: {"db":"ok","redis":"ok","ollama":"ok"}
```

#### Container Status Check
```bash
docker compose ps
# All services should show "Up" with (healthy) status
```

#### Database Connection Test
```bash
docker compose exec db psql -U salesbot -d salesbot_db -c "SELECT NOW();"
# Expected: Current timestamp
```

#### Redis Connection Test
```bash
docker compose exec redis redis-cli ping
# Expected: PONG
```

#### Worker Health Check
```bash
docker compose ps | grep worker
# Expected: "Up ... (healthy)"
```

### Automated Monitoring Setup

#### Prometheus Metrics (Optional)
```bash
# Add to docker-compose.yml (future enhancement):
prometheus:
  image: prom/prometheus:latest
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"
```

#### Health Check Cron Job
```bash
# Add to crontab (check every 5 minutes)
*/5 * * * * curl -s http://localhost:8000/ready | grep -q "ready" || /path/to/alert.sh
```

---

## Troubleshooting Guide

### Issue 1: API Not Responding

**Symptom:** `curl http://localhost:8000/health` → Connection refused

**Diagnosis:**
```bash
# Check if API container is running
docker compose ps | grep api

# Check API logs
docker compose logs api --tail=50
```

**Solutions:**
1. **API not started**
   ```bash
   docker compose up -d api
   wait 30 seconds
   curl http://localhost:8000/health
   ```

2. **Port conflict**
   ```bash
   # Check what's using port 8000
   lsof -i :8000
   # Kill if needed or change docker-compose port
   ```

3. **Image build issue**
   ```bash
   docker compose build --no-cache api
   docker compose restart api
   ```

**Resolution:** Once `curl http://localhost:8000/health` returns ok, issue is resolved

---

### Issue 2: Database Connection Failed

**Symptom:** `{"db":"error"}` in ready check

**Diagnosis:**
```bash
# Check PostgreSQL container
docker compose ps | grep db

# Check database logs
docker compose logs db --tail=50

# Verify connection string
echo $DATABASE_URL
```

**Solutions:**
1. **DB not healthy**
   ```bash
   docker compose restart db
   docker compose exec db pg_isready -U salesbot
   ```

2. **Invalid credentials**
   - Verify DATABASE_URL in docker-compose.yml
   - Check POSTGRES_PASSWORD matches

3. **Data corruption**
   ```bash
   # Rebuild database from backup
   docker compose down -v
   docker compose up -d db
   docker compose exec db psql -U salesbot -d salesbot_db < /path/to/backup.sql
   ```

---

### Issue 3: Redis Connection Failed

**Symptom:** `{"redis":"error"}` in ready check

**Diagnosis:**
```bash
docker compose logs redis --tail=50
docker compose exec redis redis-cli ping
```

**Solutions:**
1. **Redis not healthy**
   ```bash
   docker compose restart redis
   docker compose exec redis redis-cli ping
   ```

2. **Port conflict**
   ```bash
   docker compose down redis
   docker compose up -d redis
   ```

3. **Data loss**
   ```bash
   # Clear Redis cache (safe, will be repopulated)
   docker compose exec redis redis-cli FLUSHALL
   ```

---

### Issue 4: Slow Message Processing

**Symptom:** Message takes >10 seconds to process

**Diagnosis:**
```bash
# Check LLM provider response time
time curl -s https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY"

# Check database query performance
docker compose exec db psql -U salesbot -d salesbot_db \
  -c "SELECT query, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 5;"

# Monitor container resources
docker stats
```

**Solutions:**
1. **LLM rate limited**
   ```bash
   # Wait 1-2 minutes, retry
   # Groq free tier has rate limits (~30 req/min)
   ```

2. **Database slow query**
   ```bash
   # Add index to slow column
   docker compose exec db psql -U salesbot -d salesbot_db \
    -c "CREATE INDEX idx_tenant_id ON messages(tenant_id);"
   ```

3. **Resource constrained**
   - Check `docker stats` for memory/CPU usage
   - Increase Docker resource limits
   - Consider horizontal scaling

---

### Issue 5: Worker Not Processing Follow-ups

**Symptom:** Follow-up jobs stuck in queue

**Diagnosis:**
```bash
# Check worker status
docker compose ps | grep worker

# Check worker logs
docker compose logs worker --tail=100

# Check Redis queue
docker compose exec redis redis-cli LLEN rq:queue:default
```

**Solutions:**
1. **Worker crashed**
   ```bash
   docker compose restart worker
   ```

2. **Queue backed up**
   ```bash
   # Clear old jobs (WARNING: destructive)
   docker compose exec redis redis-cli FLUSHDB
   ```

3. **Redis connection lost**
   - Restart Redis (see Issue 3)
   - Verify REDIS_URL in worker config

---

### Issue 6: Configuration Not Applied

**Symptom:** Changed .env but API still uses old config

**Cause:** `@lru_cache` in `get_settings()` caches config on first import

**Solution:**
```bash
# NEVER use: docker compose restart api
# This keeps cached settings in memory

# ALWAYS use: Recreate container
docker compose down api
docker compose up -d api
```

**Important:** Environment variable changes require full container recreation, not just restart.

---

## Scaling & Performance

### Vertical Scaling (Single Machine)

**Current Configuration:**
- API: 1 instance
- Worker: 1 instance
- Database: Single instance
- Redis: Single instance

**To increase capacity:**

1. **Increase container resource limits**
   ```yaml
   # In docker-compose.yml
   api:
     # ... existing config
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 2G
   ```

2. **Increase worker processes**
   ```bash
   # In docker-compose.yml, add more worker instances
   worker-2:
     image: universal-sales-automation-core-worker
     # Same config as worker, different container name
   worker-3:
     image: universal-sales-automation-core-worker
   ```

3. **Optimize database**
   ```bash
   # Add indexes for common queries
   docker compose exec db psql -U salesbot -d salesbot_db << 'EOF'
   CREATE INDEX idx_tenant_leads ON leads(tenant_id, created_at DESC);
   CREATE INDEX idx_conversation_tenant ON conversations(lead_id);
   CREATE INDEX idx_message_conversation ON messages(conversation_id);
   EOF
   ```

### Horizontal Scaling (Multiple Machines)

**Architecture:**
```
Load Balancer (NGINX/HAProxy)
    ↓
    ├─ API Instance 1 (Machine A)
    ├─ API Instance 2 (Machine B)
    └─ API Instance 3 (Machine C)

Shared Services (Dedicated Machine):
    ├─ PostgreSQL
    ├─ Redis
    └─ Ollama
```

**Implementation:**
1. Deploy shared services to central machine
2. Deploy multiple API instances to different machines
3. Configure load balancer to round-robin requests
4. Use connection pooling for database
5. Monitor all instances from central dashboard

---

## Backup & Recovery

### Database Backup

#### Automated Daily Backup
```bash
# Add to crontab
0 2 * * * docker compose exec db pg_dump -U salesbot salesbot_db | gzip > /backups/db_$(date +\%Y\%m\%d).sql.gz
```

#### Manual Backup
```bash
docker compose exec db pg_dump -U salesbot salesbot_db > backup_$(date +%Y%m%d_%H%M%S).sql
gzip backup_*.sql
```

#### Backup Verification
```bash
gunzip -t backup_20260331.sql.gz
# Expected: No output (archive is good)
```

### Database Recovery

#### From Backup
```bash
# 1. Stop services
docker compose down

# 2. Start database only
docker compose up -d db

# 3. Restore backup
gunzip < backup_20260331.sql.gz | \
  docker compose exec -T db psql -U salesbot -d salesbot_db

# 4. Verify
docker compose exec db psql -U salesbot -d salesbot_db \
  -c "SELECT COUNT(*) FROM leads;"

# 5. Restart all services
docker compose up -d
```

### Redis Data Persistence

**Current Setup:** Redis data stored in `redis_data` volume

**To preserve data across restarts:**
- Volume is persistent (already configured)
- Automatic backup happens via Redis RDB

**To clear Redis (if needed):**
```bash
docker compose down redis -v
docker compose up -d redis
```

---

## Maintenance Schedule

### Daily Tasks
- [ ] Check `/health` endpoint (automated)
- [ ] Check `/ready` endpoint (automated)
- [ ] Monitor error logs

### Weekly Tasks
- [ ] Review message processing metrics
- [ ] Check database size: `docker compose exec db du -sh /var/lib/postgresql/data`
- [ ] Verify backups exist and are recent

### Monthly Tasks
- [ ] Test backup restoration procedure
- [ ] Review and clean up old logs
- [ ] Performance analysis (`docker stats` historical data)
- [ ] Security update check (base images)

### Quarterly Tasks
- [ ] Full system backup and restoration test
- [ ] Capacity planning review
- [ ] Documentation update
- [ ] Cost analysis (if cloud-hosted)

---

## Log Analysis

### View Logs

#### Real-time API logs
```bash
docker compose logs -f api
```

#### Last 100 lines
```bash
docker compose logs api --tail=100
```

#### With timestamps
```bash
docker compose logs api --timestamps
```

#### Specific time range
```bash
docker compose logs api --since 2026-03-31T10:00:00 --until 2026-03-31T12:00:00
```

### Log Patterns

#### Normal operation (no errors)
```
INFO:     Application startup complete
INFO:     message_classified
INFO:     escalation_created
INFO:     message_sent
```

#### Errors to investigate
```
ERROR:     (look for "ERROR" in logs)
Exception: (any exception)
Timeout: (LLM or database timeout)
ConnectionError: (service connection failed)
```

### Log Rotation (Future)

Add to docker-compose.yml:
```yaml
api:
  logging:
    driver: "json-file"
    options:
      max-size: "100m"
      max-file: "10"
```

---

## Security Procedures

### API Key Management

**Current:** Single API_SECRET_KEY in docker-compose.yml

**Security Best Practices:**
1. **Never commit .env or docker-compose.yml with real keys**
2. **Use different keys per environment:**
   - Development: `dev-key-2024`
   - Staging: `staging-key-xxxx`
   - Production: Generate new secure key

3. **Rotate keys quarterly:**
   ```bash
   # Generate new key
   python -c "import secrets; print(secrets.token_urlsafe(32))"

   # Update docker-compose.yml
   # Restart API
   docker compose down api
   docker compose up -d api
   ```

### LLM API Key Security

**Current:** Groq API key in docker-compose.yml

**Security Practices:**
1. **Use API key with minimal permissions** (if supported by provider)
2. **Monitor usage** for unusual patterns
3. **Rotate quarterly** or if suspected compromise
4. **Never expose in logs or error messages**

### Database Credentials

**Current:** Default credentials (salesbot:salesbot_secret)

**Production Recommendations:**
1. Change POSTGRES_PASSWORD from default
2. Use strong password: `python -c "import secrets; print(secrets.token_urlsafe(16))"`
3. Limit database connections:
   ```sql
   ALTER ROLE salesbot WITH CONNECTION LIMIT 20;
   ```
4. Enable SSL for remote connections

### WhatsApp Credentials

**Current:** Meta sandbox tokens in docker-compose.yml

**Security:**
1. Never share WHATSAPP_ACCESS_TOKEN
2. Regenerate if suspected compromise
3. Use webhook signature verification (already enabled)
4. Test webhook signature validation regularly

---

## Incident Response

### Message Processing Failure

**Detection:**
- API returns error response
- Lead not created in database

**Response:**
```bash
# 1. Check API logs
docker compose logs api --tail=50 | grep -i "error"

# 2. Check database
docker compose exec db psql -U salesbot -d salesbot_db \
  -c "SELECT * FROM leads ORDER BY created_at DESC LIMIT 1;"

# 3. Check LLM provider status
# Visit Groq dashboard or run health check

# 4. If LLM down, system will fallback to Ollama (slower but works)

# 5. Log incident in INCIDENT_LOG.md
```

### Database Down

**Detection:** `curl http://localhost:8000/ready` shows `"db":"error"`

**Response:**
```bash
# 1. Check database container
docker compose ps | grep db

# 2. Restart database
docker compose restart db

# 3. Verify recovery
docker compose exec db pg_isready -U salesbot

# 4. If not recovered, restore from backup (see Backup & Recovery section)
```

### High Memory Usage

**Detection:** `docker stats` shows API container using >80% memory

**Response:**
```bash
# 1. Check for memory leaks
docker compose logs api | grep -i "memory\|oom"

# 2. Identify heavy queries
docker compose exec db psql -U salesbot -d salesbot_db \
  -c "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# 3. Restart if necessary
docker compose restart api

# 4. Consider increasing container memory limit
```

---

## Documentation References

- **Architecture:** See `Universal_Sales_Automation_Core_Master_Pack_v1.md`
- **API Docs:** `http://localhost:8000/docs` (Swagger UI)
- **Email Integration:** See `EMAIL_INTEGRATION.md`
- **Test Suite:** See `TASK_6_TEST_EXPANSION_REPORT.md`
- **Deployment:** See `DEPLOY_LOG_STAGING.md`

---

## Support & Escalation

### Tier 1 Support (Routine Issues)
- Restart service
- Check logs
- Verify configurations
- Reference this runbook

### Tier 2 Support (Database/Infrastructure)
- Database backup/restore
- Capacity scaling
- Network connectivity
- Contact infrastructure team

### Tier 3 Support (Development)
- Code-level debugging
- API enhancement
- Schema changes
- Contact development team

---

## Sign-Off

**Runbook Version:** 1.0
**Last Updated:** 2026-03-31
**Next Review:** 2026-06-30
**Status:** APPROVED FOR PRODUCTION USE

**Maintained By:** DevOps Team
**Emergency Contact:** [Contact info]

---

**Operations Runbook:** ✅ READY FOR PRODUCTION
