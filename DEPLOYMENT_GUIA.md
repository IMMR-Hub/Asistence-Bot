# 📦 GUÍA DEPLOYMENT A PRODUCCIÓN v1.0

**Fecha creación:** 2026-04-01
**Versión código:** Orchestrator 100/100 (con timeouts Twilio-safe)
**Duración estimada:** 2-3 horas total

---

## 🎯 OBJETIVO FINAL
Tener el bot funcionando 24/7 con tu primer cliente real en WhatsApp, con respuestas humanizadas y manejo de urgencias.

---

## 🔴 CRÍTICO - Por qué tu Twilio falló hoy

```
Tu setup anterior:
  LLM_TIMEOUT = 30 segundos
  Twilio WhatsApp timeout = ~25 segundos
  → Twilio mata conexión ANTES que responda el bot ❌

Tu nuevo setup (ESTE):
  LLM_TIMEOUT = 8 segundos (principal)
  LLM_TIMEOUT_FALLBACK = 16 segundos
  → Ambas responden < 25s de Twilio ✅
```

**Result:** Respuestas humanizadas + urgencias manejadas correctamente.

---

## 📋 FASE 1: SETUP CREDENCIALES (30 min)

### 1.1 Obtener Credenciales Twilio

**Tu nuevo cliente será cliente Twilio (no meta WhatsApp Business)**

**Pasos:**
1. Ve a https://console.twilio.com
2. Login con tu account Twilio
3. Click en "Account"
4. Copia tu **Account SID** (empieza con "AC")
   ```
   Ejemplo: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
5. Click en "Auth Token" (si dice "Hide", primero revela)
6. Copia el **Auth Token** (40 caracteres aleatorios)
   ```
   Ejemplo: 186fb27a34ace9bf0d028db6b6d30100
   ```
7. Ve a "Phone Numbers" en el menú izquierdo
8. Si TIENES un número Twilio asignado, copia el número en formato +1234567890
   - Si NO tienes, cómpra uno aquí: https://www.twilio.com/console/phone-numbers/incoming
   - Costo: ~$1 USD/mes
   - Elige el país según dónde viva tu cliente
   - **Para Paraguay:** Usa un +1 (USA) es lo más común, o busca +595 si existe

**Resultado esperado en .env.production:**
```
TWILIO_ACCOUNT_SID_OPTIONAL=ACxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN_OPTIONAL=186fb27a34ace9bf0d028db6b6d30100
TWILIO_WHATSAPP_NUMBER_OPTIONAL=+1415-523-8886
```

---

### 1.2 Llenar .env.production

Ya existe `C:\Users\Daniel\universal-sales-automation-core\.env.production`

**Edita estos campos CRÍTICOS:**

```bash
# BASE DE DATOS (elige UNA opción)
# Opción A: Subirlo a AWS RDS (recomendado)
DATABASE_URL=postgresql+asyncpg://admin:StrongPassword123@sales-db.xxxxx.rds.amazonaws.com:5432/salesbot_prod

# Opción B: Usar PostgreSQL local en tu servidor
DATABASE_URL=postgresql+asyncpg://salesbot_prod:StrongPassword123@localhost:5432/salesbot_prod

# REDIS (elige UNA opción)
# Opción A: AWS ElastiCache (recomendado)
REDIS_URL=redis://default:StrongPassword@sales-cache.xxxxx.ng.0001.cache.amazonaws.com:6379/0

# Opción B: Local
REDIS_URL=redis://localhost:6379/0

# GROQ API KEY (obligatorio para producción)
LLM_API_KEY=gsk_YOUR_REAL_API_KEY_HERE
# Obtener en: https://console.groq.com/keys (es gratis, cuota de 30 req/min)

# TWILIO (CRÍTICO)
TWILIO_ACCOUNT_SID_OPTIONAL=ACxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN_OPTIONAL=186fb27a34ace9bf0d028db6b6d30100
TWILIO_WHATSAPP_NUMBER_OPTIONAL=+1415-523-8886

# TIMEZONE DEL CLIENTE (importante para saludos)
DEFAULT_TIMEZONE=America/Asuncion  # Para Paraguay

# API SECRET (genera algo random)
API_SECRET_KEY=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

**⚠️ NUNCA commitees .env.production a Git**

---

## 🌐 FASE 2: DEPLOY A SERVIDOR (1 hora)

### 2.1 Elegir Servidor

**Opciones recomendadas:**

| Opción | Costo | Setup | Recomendación |
|--------|-------|-------|---|
| **AWS EC2** | $5-20/mes | Complejo | Mejor para scale, credibilidad con cliente |
| **DigitalOcean** | $5-15/mes | Fácil | Mejor para MVP, muy rápido |
| **Heroku** | $7-50/mes | Super fácil | Buen balance |
| **Render** | Gratis-$12/mes | Fácil | Bueno para demo |

**Para tu PRIMER cliente, recomiendo DigitalOcean (Droplet):**
- $5/mes por 1GB RAM + 25GB SSD
- Simple deploy con Docker
- Buen uptime (99.9%)

### 2.2 Deploy en DigitalOcean (30 min)

**Pasos:**
1. Ve a https://www.digitalocean.com
2. Crea cuenta y añade tarjeta de crédito
3. Click "Create" → "Droplets"
4. Elige:
   - Image: Ubuntu 22.04
   - Size: $5/mes (1GB RAM, 1 vCPU)
   - Region: San Francisco o Toronto (cerca de USA/Twilio)
   - SSH Key: (crea uno o usa password)
5. Click "Create Droplet"
6. Espera 30s hasta que asigne IP (ej: 192.168.1.100)

**Luego, SSH al droplet:**
```bash
ssh root@192.168.1.100
# Acepta fingerprint

# Instala Docker y Docker Compose
apt-get update
apt-get install -y docker.io docker-compose
systemctl start docker

# Clona tu código
cd /home
git clone https://github.com/tuuser/universal-sales-automation-core.git
cd universal-sales-automation-core

# Copia .env.production (que llenaste en Fase 1)
# SCP desde tu máquina local:
# scp .env.production root@192.168.1.100:/home/universal-sales-automation-core/

# Verifica que .env.production esté presente
ls -la .env.production

# Levanta containers
docker-compose -f docker-compose.prod.yml up -d

# Verifica logs
docker-compose -f docker-compose.prod.yml logs -f api
```

**Resultado esperado:**
```
❯ docker-compose -f docker-compose.prod.yml logs api
api_prod_1 | INFO: Uvicorn running on http://0.0.0.0:8000
api_prod_1 | startup: env=production port=8000
api_prod_1 | db_connected ✅
```

---

### 2.3 Configurar Twilio Webhook

**Twilio necesita saber dónde ENVIAR los mensajes de WhatsApp**

**Pasos:**
1. Ve a https://console.twilio.com/
2. Click "Messaging" → "Channels" → "WhatsApp"
3. Click en tu número Twilio
4. En "Webhook URL" (o "Message Webhook"), configura:
   ```
   https://tu-ip-o-dominio.com:8000/webhooks/twilio/message
   ```
   Ejemplo:
   ```
   https://192.168.1.100:8000/webhooks/twilio/message
   ```
5. Método: **POST**
6. Click "Save"

**⚠️ Si usas IP pública (192.168.1.100), necesitas HTTPS**
- Opción A: Compra certificado SSL ($10/año en Namecheap)
- Opción B: Usa Let's Encrypt (gratis):
  ```bash
  # En el droplet:
  apt-get install -y certbot python3-certbot-nginx
  certbot certonly --standalone -d tu-dominio.com
  ```
- Opción C: Usa CloudFlare Tunnel (gratis, protege tu IP)

**Para MVP/demo, usa CloudFlare Tunnel:**
```bash
# En tu droplet:
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
dpkg -i cloudflared.deb
cloudflared tunnel create sales-bot
# Te da una URL tipo: sales-bot-xxxx.cfargotunnel.com

# Configura en Twilio:
https://sales-bot-xxxx.cfargotunnel.com/webhooks/twilio/message
```

---

## ✅ FASE 3: TEST & VALIDACIÓN (30 min)

### 3.1 Test Local (Antes de ir a cliente)

```bash
# En tu máquina local, con Docker levantado:
curl -X POST http://localhost:8000/health
# Esperado: {"status": "ok"}

# Test del webhook:
curl -X POST http://localhost:8000/webhooks/twilio/message \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp%3A%2B595123456789&Body=Hola%20Sofia&MessageSid=SM123456"
# Esperado: {"success": true} o similar
```

### 3.2 Test con Cliente (End-to-End)

1. **Informa al cliente:**
   > "Tu bot está listo. Mándame un mensaje por WhatsApp a este número: +1415-523-8886"

2. **Cliente envía:** "Hola, ¿qué horarios tienen?"
   - Bot responde: "¡Hola! Soy Sofía, recepcionista del consultorio..." ✅

3. **Cliente envía:** "Me duele la espalda"
   - Bot responde: "¡Ay, qué molestia! Le aviso al doctor. ¿Me das tu nombre completo?" ✅
   - Estado: **ESCALADA** (humano atiende)

4. **Cliente envía:** "Gracias!"
   - Bot NO responde (estado SILENCE) ✅

### 3.3 Monitoreo

```bash
# Ver logs en producción:
docker-compose -f docker-compose.prod.yml logs -f api

# Ver estado de containers:
docker-compose -f docker-compose.prod.yml ps

# Restart si es necesario:
docker-compose -f docker-compose.prod.yml restart api
```

---

## 📊 CHECKLIST PRE-CLIENTE

- [ ] .env.production llenado con credenciales reales
- [ ] docker-compose.prod.yml levantado sin errores
- [ ] Base de datos conectada (`db_connected` en logs)
- [ ] Twilio webhook configurado
- [ ] Test local: `curl /health` retorna 200
- [ ] Test Twilio: envío un mensaje, bot responde en < 8s
- [ ] Cliente logra conectarse y enviar mensaje
- [ ] Urgencia detectada y escalada correctamente
- [ ] Respuestas humanizadas (no robóticas)

---

## 🔥 TROUBLESHOOTING RÁPIDO

### Bot no responde a mensajes Twilio
```
Causa: Webhook no configurado o URL incorrecta
Solución: Ve a Twilio Console → Messaging → Webhook, verifica URL
```

### LLM timeout (respuesta muy lenta)
```
Causa: Groq API key inválida o rate limit
Solución: Verifica .env.production LLM_API_KEY
Fallback a Ollama se activa automáticamente
```

### Database connection failed
```
Causa: DATABASE_URL incorrecta
Solución: Verifica conexión a PostgreSQL:
  psql postgresql://user:pass@host:5432/db
```

### "Response sent but no JSON" error
```
Causa: Orchestrator no retornó JSON válido
Solución: Ver logs, Groq puede estar fallando
```

---

## 💡 PRÓXIMOS PASOS (Después de Fase 3)

1. **Obtener dominio:** compra dominio en Namecheap ($10/año)
   - Ej: `mi-consultorio.com`
   - Apunta DNS a tu IP DigitalOcean
   - Configura SSL con Let's Encrypt

2. **Análytics:** implementar dashboard de conversaciones
   - Cuántos mensajes recibidos/respondidos
   - Tasa de escaladas
   - Tiempo de respuesta promedio

3. **Multi-tenant:** agregar más clientes (tu código YA soporta esto)
   - Cada cliente tiene su propia config en DB
   - Mismo bot sirve a todos

4. **Mejoras UX:**
   - Preguntas de clasificación ("¿Cita o urgencia?")
   - Feedback del cliente ("¿Te ayudé?")
   - Horarios dinámicos

---

## 📞 CONTACTO CLIENTE

**Template para informar al cliente:**

---

> ¡Hola [Cliente]!
> Tu bot de WhatsApp está listo 🎉
>
> **Nombre:** Sofía (tu recepcionista virtual)
> **Número:** +1415-523-8886
> **Disponibilidad:** 24/7 automático
>
> **Qué hace:**
> - Recibe mensajes sobre citas, urgencias, preguntas
> - Responde humanizado (como una recepcionista real)
> - Si es urgencia, escala al doctor
> - Si es cita, ofrece horarios disponibles
>
> **Prueba ahora:** Abre WhatsApp, busca +1415-523-8886, envía "Hola"
>
> Cualquier problema, avísame.

---

**Fin de DEPLOYMENT_GUIA.md**
