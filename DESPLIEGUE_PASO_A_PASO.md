# 🚀 DESPLIEGUE PASO A PASO - A PRUEBA DE TONTOS

**Fecha**: 2026-04-02
**Duración**: 2-3 horas (si todo va bien)
**Dificultad**: Fácil (no necesitas experiencia en DevOps)

---

## Opción 1: DESPLIEGUE LOCAL RÁPIDO (Para pruebas hoy) ⚡

### ✅ Ventajas:
- Cero costo
- Resultado en 30 minutos
- Perfecto para demostración
- Sin dependencias externas

### ❌ Desventajas:
- Solo funciona en tu máquina
- No es accesible desde internet
- No para clientes reales

### Para demostración local (QUE YA ESTÁ FUNCIONANDO):

```bash
# 1. Verifica que todo esté funcionando
cd C:\Users\Daniel\universal-sales-automation-core

# 2. Arranca los containers (si no están corriendo)
docker-compose up -d

# 3. Espera 10 segundos y verifica salud
curl http://localhost:8000/api/health

# Deberías ver: {"status":"ok"}
```

**✅ LISTO PARA DEMOSTRACIÓN LOCAL**

---

## Opción 2: DESPLIEGUE EN PRODUCCIÓN (Para cliente real) 🌐

Esta es la que necesitas para mostrarle a tu primer cliente.

### Requisitos Previos:
1. **Tarjeta de crédito** (para DigitalOcean)
2. **Cuenta Twilio del cliente** (para números WhatsApp)
3. **30 minutos de tiempo**

---

## PASO 1: Crear Cuenta en DigitalOcean

### ¿Por qué DigitalOcean?
- Barato ($12/mes)
- Fácil de usar
- Excelente para startups
- Buen soporte

### Pasos:

1. **Ve a**: https://www.digitalocean.com/

2. **Haz clic en "Sign Up"** (esquina superior derecha)

3. **Rellena el formulario**:
   - Email: tu email
   - Password: contraseña fuerte
   - Full Name: tu nombre

4. **Verifica tu email**

5. **Añade método de pago**:
   - Haz clic en "Billing" (arriba a la izquierda)
   - Haz clic en "Add Payment Method"
   - Sube tu tarjeta de crédito

6. **¡Listo!** Ya tienes cuenta en DigitalOcean

---

## PASO 2: Crear un Droplet (Servidor Virtual)

Un **Droplet** es un servidor virtual en la nube. Es tu máquina en internet.

### Pasos:

1. **En el panel de DigitalOcean**, haz clic en "Create" (botón azul arriba)

2. **Selecciona "Droplets"** (primera opción)

3. **Configura el Droplet**:

```
REGION:
  → Elige la más cercana a tu cliente
     (América del Sur: São Paulo o similar)

IMAGE:
  → Ubuntu 24.04 LTS

SIZE:
  → Selecciona: 2 GB RAM / 50 GB SSD ($12/month)
    (Esto es suficiente para empezar)

ADD IMPROVEMENTS:
  → Dejar como está

SSH KEY (IMPORTANTE):
  → Haz clic en "New SSH Key"
  → Dale nombre: "salesbot-prod"
  → En tu máquina (PowerShell como Admin), corre:

  ssh-keygen -t rsa -b 4096 -f "$env:USERPROFILE\.ssh\salesbot-prod"

  → Copia el contenido de:

  Get-Content "$env:USERPROFILE\.ssh\salesbot-prod.pub"

  → Pégalo en DigitalOcean
  → Haz clic en "Add SSH Key"

HOSTNAME:
  → salesbot-prod (o el nombre que prefieras)

ENABLE BACKUPS:
  → ☑️ Sí, habilitar (costo adicional pequeño)
```

4. **Haz clic en "Create Droplet"**

5. **Espera 2-3 minutos** a que se cree

6. **Copia la IP pública** que aparece (algo como 192.0.2.1)

---

## PASO 3: Conectar al Droplet vía SSH

SSH te permite conectar a tu servidor desde tu máquina.

### En PowerShell (como Admin):

```powershell
# Reemplaza 192.0.2.1 con tu IP real
ssh -i "$env:USERPROFILE\.ssh\salesbot-prod" root@192.0.2.1

# En la primera conexión, dirá:
# "The authenticity of host can't be established"
# Escribe: yes

# ¡Ahora estás conectado al servidor!
# Deberías ver algo como: root@salesbot-prod:~#
```

**Si funciona**: ✅ Continúa
**Si no funciona**: Ver sección "Solucionar problemas" abajo

---

## PASO 4: Instalar Docker en el Droplet

Una vez conectado vía SSH, corre estos comandos:

```bash
# 1. Actualiza el sistema
apt update && apt upgrade -y

# Esto puede tardar 2-3 minutos. Espera a que termine.

# 2. Instala Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 3. Instala Docker Compose
apt install -y docker-compose

# 4. Verifica la instalación
docker --version
docker-compose --version

# Deberías ver versiones (v24+, v2+)
```

**Si ves versiones**: ✅ Docker instalado correctamente

---

## PASO 5: Descargar tu Código en el Servidor

Aún en SSH:

```bash
# 1. Ve al directorio correcto
cd /opt

# 2. Clona el repositorio
git clone https://github.com/tu-usuario/universal-sales-automation-core.git

# Si no tienes un repo en GitHub:
# Sube los archivos manualmente:
#   a) En el Droplet, crea la carpeta:
#      mkdir -p /opt/universal-sales-automation-core
#   b) Copia los archivos desde tu PC
#      scp -r -i ssh-key C:\...\universal-sales-automation-core/* root@IP:/opt/universal-sales-automation-core/

# 3. Entra a la carpeta
cd universal-sales-automation-core

# 4. Verifica que los archivos están
ls -la

# Deberías ver: docker-compose.yml, requirements.txt, app/, etc.
```

---

## PASO 6: Configurar Variables de Entorno

Esta es la parte MÁS IMPORTANTE. Aquí pones las credenciales reales.

```bash
# 1. Copia el template
cp .env.production .env.prod

# 2. Abre el archivo para editar
nano .env.prod

# Ahora estás en el editor nano. Busca estas líneas y REEMPLÁZALAS:

# ═══════════════════════════════════════════════════════════════
# ENCUENTRA ESTO                          Y REEMPLÁZALO CON ESTO
# ═══════════════════════════════════════════════════════════════

DATABASE_URL=postgresql+asyncpg://...    → postgresql+asyncpg://salesbot:password@127.0.0.1:5432/salesbot_db

REDIS_URL=redis://CHANGE_ME_HOST:...     → redis://127.0.0.1:6379/0

LLM_API_KEY=gsk_YOUR_REAL_API_KEY_HERE   → gsk_XXXXXXXXXXXXX (Tu API key de Groq)

TWILIO_ACCOUNT_SID_OPTIONAL=ACxx...      → ACxxxxxxxxxxxxxxxxxxxxxx (De Twilio)

TWILIO_AUTH_TOKEN_OPTIONAL=...           → your_auth_token (De Twilio)

TWILIO_WHATSAPP_NUMBER_OPTIONAL=+1...    → +1415-523-8886 (Tu número de Twilio)

API_SECRET_KEY=change-this...            → (Genera: python -c "import secrets; print(secrets.token_urlsafe(32))")

WHATSAPP_VERIFY_TOKEN=changeme           → (Genera: python -c "import secrets; print(secrets.token_hex(16))")

# ═══════════════════════════════════════════════════════════════

# Para editar en nano:
# 1. Presiona Ctrl+X para salir
# 2. Cuando pregunta "Save?", presiona Y
# 3. Presiona Enter para confirmar

# IMPORTANTE: Si no tienes credenciales aún:
# Usa las de PRUEBA (localhost), y cámbialo después para cliente real
```

### ¿Cómo obtener las credenciales?

**Groq API Key** (LLM):
1. Ve a: https://console.groq.com/keys
2. Crea una cuenta (gratis)
3. Copia la API key
4. Pégala en `LLM_API_KEY=gsk_...`

**Twilio** (WhatsApp):
1. Ve a: https://www.twilio.com/console
2. Crea una cuenta (o usa la existente del cliente)
3. Account Info → Account SID (cópialo)
4. Account Info → Auth Token (cópialo)
5. WhatsApp → Sandbox → Número (cópialo)
6. Pégalo todo en el .env.prod

**API Secret Key** y **Verify Token**:
```bash
# Genera números aleatorios seguros:
python3 << 'EOF'
import secrets
print("API_SECRET_KEY:", secrets.token_urlsafe(32))
print("WHATSAPP_VERIFY_TOKEN:", secrets.token_hex(16))
EOF

# Copia los resultados en el .env.prod
```

---

## PASO 7: Arrancar los Containers

Aún en SSH, en la carpeta `/opt/universal-sales-automation-core`:

```bash
# 1. Arranca todos los servicios
docker-compose --env-file .env.prod up -d

# 2. Espera 20 segundos (los containers se están iniciando)

# 3. Verifica que todo esté corriendo
docker-compose ps

# Deberías ver algo como:
# NAME              STATUS
# salesbot_db       Up (healthy)
# salesbot_redis    Up (healthy)
# salesbot_api      Up
# salesbot_worker   Up (healthy)
# salesbot_ollama   Up

# Si ves "Up (healthy)" en todos = ✅ TODO BIEN
```

---

## PASO 8: Ejecutar Migraciones de Base de Datos

```bash
# Crea la estructura de la BD
docker-compose exec api alembic upgrade head

# Deberías ver:
# INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# INFO  [alembic.runtime.migration] Running upgrade  -> 001_...
# INFO  [alembic.runtime.migration] Running upgrade 001 -> 002_...

# Si ves eso = ✅ Base de datos inicializada
```

---

## PASO 9: Crear un Tenant (Cliente) en la Base de Datos

```bash
# Accede a la BD
docker-compose exec db psql -U salesbot -d salesbot_db

# Ejecuta este comando (dentro de psql):
INSERT INTO tenants (id, slug, name, created_at, updated_at)
VALUES (
  gen_random_uuid(),
  'primer-cliente',
  'Clínica Demo',
  NOW(),
  NOW()
);

# Presiona Enter

# Verifica que se creó:
SELECT id, slug, name FROM tenants;

# Deberías ver una fila con tu cliente

# Para salir de psql:
\q
```

---

## PASO 10: Abrir Puertos en el Firewall

Para que internet pueda acceder a tu servidor:

```bash
# Aún en SSH

# Abre el puerto HTTP (80)
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS (para después)

# Habilita el firewall
ufw enable

# Verifica
ufw status
```

---

## PASO 11: Configurar Nginx (Opcional pero Recomendado)

Nginx es un "guardián" que dirige tráfico a tu API.

```bash
# Instala Nginx
apt install -y nginx

# Crea configuración
cat > /etc/nginx/sites-available/salesbot << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /webhooks/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Activa la configuración
ln -s /etc/nginx/sites-available/salesbot /etc/nginx/sites-enabled/
nginx -t  # Verifica sintaxis
systemctl restart nginx
```

---

## PASO 12: Obtener Tu IP y Probar

```bash
# En SSH, obtén la IP pública
curl http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address

# O simplemente ve a DigitalOcean y copia la IP del Droplet

# En tu PC, abre PowerShell:
# Reemplaza 192.0.2.1 con tu IP real

curl http://192.0.2.1/api/health

# Deberías ver: {"status":"ok"}

# ✅ ¡TU SERVIDOR ESTÁ VIVO!
```

---

## PASO 13: Registrar Webhook en Twilio

El webhook es cómo Twilio le dice a tu bot: "Hey, recibí un mensaje".

### En Twilio Console:

1. Ve a: https://www.twilio.com/console

2. Busca **Messaging** → **WhatsApp** → **Sandbox Settings**

3. En "**When a message comes in**":
   - URL: `http://192.0.2.1/webhooks/whatsapp/inbound?tenant_slug=primer-cliente`
   - Method: `POST`
   - Haz clic en **Save**

4. En "**Status Callbacks**":
   - URL: `http://192.0.2.1/webhooks/whatsapp/status`
   - Method: `POST`
   - Haz clic en **Save**

5. Abajo, verás el número de Twilio (ej: +1415-523-8886)
   - Este es el que el cliente añade a WhatsApp

---

## PASO 14: Probar el Webhook

### En PowerShell (en tu PC):

```powershell
# Reemplaza 192.0.2.1 con tu IP real

$body = "From=whatsapp%3A%2B595987654321&Body=Me%20duele%20la%20muela&MessageSid=SM123"

curl -X POST "http://192.0.2.1/webhooks/whatsapp/inbound?tenant_slug=primer-cliente" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  -Body $body

# Deberías ver:
# {"status":"ok","processed":1,"results":[...]}

# ✅ ¡EL WEBHOOK FUNCIONA!
```

---

## PASO 15: Prueba Desde WhatsApp (Prueba REAL)

1. **Abre WhatsApp en tu teléfono**

2. **Busca el número de Twilio** (ej: +1415-523-8886)
   - O usa el que Twilio te da en el Sandbox

3. **Envía un mensaje**:
   - "Hola"
   - o "Me duele la muela"
   - o "Quiero una cita"

4. **El bot debería responder en menos de 2 segundos**

5. **Si funciona**: ✅ ¡LISTO PARA CLIENTE!

6. **Si no funciona**: Ver sección "Solucionar Problemas"

---

## PASO 16: Ver Logs (Para Debugging)

Si algo no funciona, aquí puedes ver qué pasó:

```bash
# Aún en SSH en el Droplet

# Ver últimos 50 líneas de logs
docker-compose logs -f api --tail=50

# Ver solo errores
docker-compose logs api | grep -i error

# Ver eventos en tiempo real
docker-compose logs -f api

# Presiona Ctrl+C para salir
```

---

## PASO 17: Configurar SSL/HTTPS (Opcional pero Recomendado)

Para que sea seguro (🔒 en lugar de ⚠️):

```bash
# Instala Certbot
apt install -y certbot python3-certbot-nginx

# Obtén certificado gratuito (Let's Encrypt)
certbot certonly --nginx -d tudominio.com

# Si no tienes dominio aún, salta esto
# (Puedes hacerlo después)

# Para autorenovación:
systemctl enable certbot.timer
```

---

## PASO 18: Configurar Backups Automáticos

Importante: Haz backup de tu base de datos todos los días.

```bash
# En SSH en el Droplet

# Crea carpeta para backups
mkdir -p /backups

# Crea script de backup
cat > /opt/backup-db.sh << 'EOF'
#!/bin/bash
cd /opt/universal-sales-automation-core
docker-compose exec -T db pg_dump -U salesbot salesbot_db | gzip > /backups/db_$(date +%Y%m%d).sql.gz
echo "Backup created: /backups/db_$(date +%Y%m%d).sql.gz"
EOF

# Hazlo ejecutable
chmod +x /opt/backup-db.sh

# Programa para que corra a las 2 AM todos los días
# Abre crontab
crontab -e

# Añade esta línea al final:
0 2 * * * /opt/backup-db.sh

# Presiona Ctrl+X, luego Y para guardar
```

---

## PASO 19: Monitoreo Diario

Crea un script para verificar que todo sigue funcionando:

```bash
# En SSH en el Droplet

# Crea el script
cat > /opt/health-check.sh << 'EOF'
#!/bin/bash
echo "=== HEALTH CHECK $(date) ==="
echo ""
echo "Docker containers:"
docker-compose ps
echo ""
echo "API Health:"
curl -s http://localhost:8000/api/health | python3 -m json.tool
echo ""
echo "Database:"
docker-compose exec -T db pg_isready
EOF

chmod +x /opt/health-check.sh

# Ejecútalo manualmente:
/opt/health-check.sh

# Deberías ver todos los servicios "Up" y API respondiendo "ok"
```

---

## 🎯 CHECKLIST FINAL DE DESPLIEGUE

Antes de mostrar al cliente, verifica todo esto:

- [ ] Droplet creado en DigitalOcean
- [ ] SSH conectando correctamente
- [ ] Docker instalado y funcionando
- [ ] Código descargado en `/opt/universal-sales-automation-core`
- [ ] `.env.prod` configurado con credenciales reales
- [ ] Containers corriendo: `docker-compose ps` muestra all "Up"
- [ ] Migraciones ejecutadas: `alembic upgrade head` sin errores
- [ ] Tenant creado en BD
- [ ] Firewall abierto en puertos 22, 80, 443
- [ ] Nginx funcionando
- [ ] Webhook registrado en Twilio
- [ ] Prueba de webhook con curl: devuelve `{"status":"ok"}`
- [ ] Prueba desde WhatsApp: bot responde en < 2 segundos
- [ ] Logs no muestran errores: `docker-compose logs api | grep -i error` vacío
- [ ] Health check pasa: curl `http://IP/api/health` devuelve `{"status":"ok"}`

---

## 🆘 SOLUCIONAR PROBLEMAS COMUNES

### Problema: "Connection refused" cuando hago SSH

**Causa**: El Droplet aún no está listo

**Solución**:
```powershell
# Espera 3-5 minutos y vuelve a intentar
ssh -i "$env:USERPROFILE\.ssh\salesbot-prod" root@192.0.2.1
```

### Problema: "command not found: docker"

**Causa**: Docker no se instaló correctamente

**Solución**:
```bash
# En SSH, ejecuta de nuevo:
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

### Problema: "ERROR: Pool "default" not found"

**Causa**: Redis no está corriendo

**Solución**:
```bash
# En SSH:
docker-compose restart redis
docker-compose up -d
docker-compose ps  # Verifica que redis está "Up"
```

### Problema: "webhook returns 404"

**Causa**: El endpoint es incorrecto o el tenant no existe

**Solución**:
```bash
# Verifica la URL:
# ❌ http://IP/webhooks/twilio/message
# ✅ http://IP/webhooks/whatsapp/inbound?tenant_slug=primer-cliente

# Verifica el tenant existe:
docker-compose exec db psql -U salesbot -d salesbot_db -c "SELECT * FROM tenants;"

# Si está vacío, créalo:
# INSERT INTO tenants (id, slug, name, created_at, updated_at)
# VALUES (gen_random_uuid(), 'primer-cliente', 'Clínica Demo', NOW(), NOW());
```

### Problema: "Bot no responde"

**Causa**: LLM (Groq) no tiene conexión o API key es inválida

**Solución**:
```bash
# Verifica que el API key está en .env.prod
grep "LLM_API_KEY" .env.prod

# Verifica que el valor no está vacío
# Si está "gsk_XXXXX..." es correcto

# Reinicia los containers:
docker-compose restart api

# Ver logs:
docker-compose logs api | tail -100 | grep -i "groq\|error"
```

### Problema: "Permission denied" en SSH

**Causa**: Clave SSH no tiene permisos

**Solución**:
```powershell
# En PowerShell (Admin):
icacls "$env:USERPROFILE\.ssh\salesbot-prod" /reset
icacls "$env:USERPROFILE\.ssh\salesbot-prod" /inheritance:r
icacls "$env:USERPROFILE\.ssh\salesbot-prod" /grant:r "$env:USERNAME`:(F)"
```

---

## 📊 MONITOREO POST-DESPLIEGUE

Una vez vivo, monitorea esto cada día:

```bash
# Crea un script que corre cada mañana:

cat > /opt/daily-check.sh << 'EOF'
#!/bin/bash
# Enviado por email o guardado en un log

echo "=== REPORTE DIARIO $(date) ==="
echo ""

# 1. Uptime del servidor
uptime

# 2. Estado de containers
echo "Containers:"
docker-compose ps

# 3. Mensajes procesados en últimas 24h
echo "Messages processed (last 24h):"
docker-compose exec -T db psql -U salesbot -d salesbot_db -c \
  "SELECT COUNT(*) as total FROM messages WHERE created_at > NOW() - INTERVAL '24 hours';"

# 4. Escalaciones en últimas 24h
echo "Escalations (last 24h):"
docker-compose exec -T db psql -U salesbot -d salesbot_db -c \
  "SELECT COUNT(*) as total FROM conversations WHERE awaiting_human_callback = true AND updated_at > NOW() - INTERVAL '24 hours';"

# 5. Errores en logs
echo "Errors in logs:"
docker-compose logs api --tail=500 | grep -i "error\|exception" | wc -l

EOF

chmod +x /opt/daily-check.sh

# Ejecútalo cada mañana:
/opt/daily-check.sh
```

---

## ✅ ¡DESPLIEGUE COMPLETADO!

Si llegaste aquí y todo funciona:

✅ Tu servidor está VIVO
✅ El bot está RESPONDIENDO
✅ Tu cliente puede USARLO
✅ Puedes ESCALAR cuando sea necesario

### Siguiente paso:
Sigue el `CLIENT_ONBOARDING_CHECKLIST.md` para onboardear al cliente.

---

**Versión**: 1.0
**Fecha**: 2026-04-02
**Duración Total**: 2-3 horas
**Costo Mensual**: ~$15-25 (después de instalación inicial)
