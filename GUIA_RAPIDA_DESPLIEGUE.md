# ⚡ GUÍA RÁPIDA - DESPLIEGUE EN 3 HORAS

**Objetivo**: Tener tu bot VIVO en internet en 3 horas
**Costo**: ~$12 USD para el servidor
**Dificultad**: Fácil (copiar y pegar comandos)

---

## 📋 PLAN DE ACCIÓN

```
AHORA (30 min)        → Pruebas locales
  ↓
1 hora después        → Crear cuenta DigitalOcean
  ↓
2 horas después       → Desplegar código
  ↓
3 horas después       → ✅ BOT VIVO EN INTERNET
```

---

## 🔧 PASO 1: PRUEBAS LOCALES (30 MIN) ✅ HAZLO AHORA

```powershell
# En PowerShell en C:\Users\Daniel\universal-sales-automation-core

# 1. Verifica que Docker está corriendo
docker-compose ps

# 2. Ejecuta tests
pytest app/tests/unit/test_orchestrator_state.py -v
# Deberías ver: 10 passed ✅

# 3. Prueba el API
curl http://localhost:8000/api/health
# Deberías ver: {"status":"ok"} ✅

# 4. Prueba un mensaje
$payload = @{
    tenant_slug = "test"
    channel = "whatsapp"
    contact_name = "Test"
    contact_phone = "+595987654321"
    text_content = "Me duele la muela"
} | ConvertTo-Json

curl -X POST http://localhost:8000/api/test/process-message `
  -H "Content-Type: application/json" `
  -Body $payload
# Deberías ver: escalated: true ✅

# SI TODO PASÓ: Continúa
```

---

## 🌐 PASO 2: CREAR CUENTA DIGITALOCEAN (10 MIN)

### Link:
https://www.digitalocean.com/

### Pasos:
1. Haz clic en "Sign Up"
2. Rellena: email, password, nombre
3. Verifica tu email
4. Añade tarjeta de crédito en "Billing"

---

## 💻 PASO 3: CREAR DROPLET (5 MIN)

1. Haz clic en "Create" (botón azul)
2. Selecciona "Droplets"
3. Configura:
   - **Region**: América del Sur (São Paulo o similar)
   - **Image**: Ubuntu 24.04 LTS
   - **Size**: 2GB RAM / 50GB SSD ($12/month)
   - **SSH Key**:
     ```powershell
     # En PowerShell (Admin):
     ssh-keygen -t rsa -b 4096 -f "$env:USERPROFILE\.ssh\salesbot-prod"
     Get-Content "$env:USERPROFILE\.ssh\salesbot-prod.pub"
     # Copia eso y pégalo en DigitalOcean
     ```
   - **Hostname**: salesbot-prod

4. Haz clic "Create Droplet"
5. **Copia la IP pública** que aparece (ej: 192.0.2.1)

---

## 🔌 PASO 4: CONECTAR AL SERVIDOR (5 MIN)

```powershell
# En PowerShell:
ssh -i "$env:USERPROFILE\.ssh\salesbot-prod" root@192.0.2.1

# Cuando preguntes "Add to known hosts?", escribe: yes
# ¡Ahora estás dentro del servidor!
```

---

## 🐳 PASO 5: INSTALAR DOCKER (10 MIN)

Aún en SSH:

```bash
# Copiar estos comandos exactamente:

apt update && apt upgrade -y

curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

apt install -y docker-compose

# Verifica:
docker --version
docker-compose --version
```

---

## 📦 PASO 6: DESCARGAR TU CÓDIGO (5 MIN)

```bash
cd /opt

git clone https://github.com/tu-usuario/universal-sales-automation-core.git
# O si no tienes en GitHub:
# mkdir -p /opt/universal-sales-automation-core
# scp -r C:\...\universal-sales-automation-core/* root@IP:/opt/

cd universal-sales-automation-core

ls -la  # Verifica que están los archivos
```

---

## ⚙️ PASO 7: CONFIGURAR VARIABLES (15 MIN) - MÁS IMPORTANTE

```bash
# Aún en SSH

cp .env.production .env.prod

nano .env.prod

# Busca y REEMPLAZA estas líneas:
```

### Valores que necesitas:

| Variable | Valor | Dónde obtenerlo |
|----------|-------|-----------------|
| `DATABASE_URL` | `postgresql+asyncpg://salesbot:password@127.0.0.1:5432/salesbot_db` | Usa este valor |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Usa este valor |
| `LLM_API_KEY` | `gsk_XXXXX...` | https://console.groq.com/keys |
| `TWILIO_ACCOUNT_SID` | `ACxxx...` | https://www.twilio.com/console |
| `TWILIO_AUTH_TOKEN` | `auth_token` | https://www.twilio.com/console |
| `TWILIO_WHATSAPP_NUMBER` | `+1415-523-8886` | https://www.twilio.com/console |
| `API_SECRET_KEY` | Genera: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` | Ejecuta ese comando |
| `WHATSAPP_VERIFY_TOKEN` | Genera: `python3 -c "import secrets; print(secrets.token_hex(16))"` | Ejecuta ese comando |

### Para editar en nano:
- Usa Ctrl+F para buscar
- Reemplaza el valor
- Presiona Ctrl+X → Y → Enter para guardar

---

## 🚀 PASO 8: ARRANCAR CONTAINERS (5 MIN)

```bash
# Aún en SSH

docker-compose --env-file .env.prod up -d

# Espera 20 segundos

# Verifica:
docker-compose ps

# Deberías ver:
# salesbot_db       Up (healthy)
# salesbot_redis    Up (healthy)
# salesbot_api      Up
# salesbot_worker   Up (healthy)
```

---

## 🗄️ PASO 9: INICIALIZAR BASE DE DATOS (5 MIN)

```bash
# Aún en SSH

docker-compose exec api alembic upgrade head

# Deberías ver:
# INFO  [alembic.runtime.migration] Running upgrade  -> 001_...
# INFO  [alembic.runtime.migration] Running upgrade 001 -> 002_...

# Crea un cliente de prueba:
docker-compose exec db psql -U salesbot -d salesbot_db << 'EOF'
INSERT INTO tenants (id, slug, name, created_at, updated_at)
VALUES (
  gen_random_uuid(),
  'cliente-demo',
  'Clínica Demo',
  NOW(),
  NOW()
);
EOF
```

---

## 🔓 PASO 10: ABRIR PUERTOS (3 MIN)

```bash
# Aún en SSH

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## 🌍 PASO 11: CONFIGURAR NGINX (10 MIN)

```bash
apt install -y nginx

cat > /etc/nginx/sites-available/salesbot << 'EOF'
server {
    listen 80;
    server_name _;
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/salesbot /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

---

## 📱 PASO 12: REGISTRAR WEBHOOK EN TWILIO (10 MIN)

1. Ve a: https://www.twilio.com/console

2. Busca: **Messaging → WhatsApp → Sandbox Settings**

3. En "**When a message comes in**":
   - URL: `http://192.0.2.1/webhooks/whatsapp/inbound?tenant_slug=cliente-demo`
   - Method: POST
   - Save

---

## ✅ PASO 13: VERIFICAR (5 MIN)

### En PowerShell (en tu PC):

```powershell
# Reemplaza 192.0.2.1 con tu IP real

# Test 1: Health check
curl http://192.0.2.1/api/health

# Deberías ver: {"status":"ok"} ✅

# Test 2: Webhook
$body = "From=whatsapp%3A%2B595987654321&Body=Me%20duele%20la%20muela&MessageSid=SM123"

curl -X POST "http://192.0.2.1/webhooks/whatsapp/inbound?tenant_slug=cliente-demo" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  -Body $body

# Deberías ver: {"status":"ok","processed":1,...} ✅
```

---

## 🎉 PASO 14: PRUEBA DESDE WhatsApp

1. Abre WhatsApp en tu teléfono
2. Busca el número de Twilio (que copiaste arriba)
3. Envía un mensaje: "Hola" o "Me duele la muela"
4. **El bot debería responder en < 2 segundos**

**Si funciona**: ✅ ¡LISTO PARA CLIENTE!

---

## 🐛 SOLUCIONAR PROBLEMAS RÁPIDO

### "curl: comando no encontrado" en PowerShell
```powershell
# En PowerShell, usa:
Invoke-WebRequest -Uri "http://192.0.2.1/api/health" -UseBasicParsing | Select-Object Content
```

### "Connection refused"
```bash
# En SSH, verifica que Docker está corriendo:
docker-compose ps
docker-compose logs api | tail -50
```

### "webhook returns 404"
- ✅ URL correcta: `http://IP/webhooks/whatsapp/inbound?tenant_slug=cliente-demo`
- ✅ Tenant existe en BD: `docker-compose exec db psql -U salesbot -d salesbot_db -c "SELECT * FROM tenants;"`

### "Bot no responde"
```bash
# En SSH:
docker-compose logs api | grep -i "groq\|error"
# Verifica que LLM_API_KEY está en .env.prod
```

---

## 📊 COMANDOS ÚTILES PARA DESPUÉS

```bash
# Ver logs en vivo
docker-compose logs -f api

# Reiniciar un servicio
docker-compose restart api

# Acceder a la BD
docker-compose exec db psql -U salesbot -d salesbot_db

# Backup rápido
docker-compose exec -T db pg_dump -U salesbot salesbot_db > backup.sql

# Ver estado
docker-compose ps
```

---

## 💰 COSTOS

| Item | Precio |
|------|--------|
| Droplet (2GB, 50GB) | $12/mes |
| Dominio | $10-15/año |
| Groq API (Free Tier) | FREE |
| Nginx | FREE |
| SSL Certificate | FREE (Let's Encrypt) |
| **TOTAL** | **~$12-13/mes** |

---

## 📋 CHECKLIST FINAL

- [ ] ✅ Docker está corriendo
- [ ] ✅ Tests locales pasan (10/10)
- [ ] ✅ Cuenta DigitalOcean creada
- [ ] ✅ Droplet creado (IP copiado)
- [ ] ✅ SSH conectando
- [ ] ✅ Docker instalado en servidor
- [ ] ✅ Código descargado
- [ ] ✅ .env.prod configurado con credenciales
- [ ] ✅ Containers arrancados (`docker-compose ps` = all Up)
- [ ] ✅ Base de datos migrada
- [ ] ✅ Tenant creado
- [ ] ✅ Puertos abiertos
- [ ] ✅ Nginx configurado
- [ ] ✅ Webhook registrado en Twilio
- [ ] ✅ Health check responde 200 OK
- [ ] ✅ Webhook test retorna success
- [ ] ✅ WhatsApp: Bot responde en < 2 segundos

**Si marcaste TODO**: ✅ **¡ESTÁ LISTO!**

---

## 🎯 PRÓXIMOS PASOS

1. **Hoy**: Completa estos pasos
2. **Mañana**: Invita al cliente a probar
3. **Semana 1**: Feedback y ajustes
4. **Semana 2**: Go-live con cliente real

---

## 📞 SOPORTE RÁPIDO

**Si algo falla**:
1. Ve a: `DESPLIEGUE_PASO_A_PASO.md` (guía detallada)
2. O: `QUICK_REFERENCE.md` (troubleshooting)

**Si tienes dudas**:
1. Lee: `README_PROJECT_STATUS.md` (arquitectura)
2. O: `PRUEBAS_FINALES_LOCALES.md` (pruebas detalladas)

---

## ✨ ¡LISTO!

**Duración total**: 2-3 horas
**Resultado**: Bot vivo en internet, responderá a clientes 24/7

**Siguiente paso**: Síguelo comando por comando. Si algo no funciona, busca la solución en la sección "Solucionar Problemas" arriba.

---

**Version**: 1.0
**Creado**: 2026-04-02
**Duración**: 3 horas
**Dificultad**: Fácil
