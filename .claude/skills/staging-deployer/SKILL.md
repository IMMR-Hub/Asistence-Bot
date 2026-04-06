# SKILL: staging-deployer

## Propósito
Ejecutar un deploy completo y verificado al ambiente de staging. No avanzar si algún paso falla.

## Pre-requisitos
Verificar antes de ejecutar:
- [ ] Docker Desktop corriendo
- [ ] `.env` con todas las variables requeridas
- [ ] No hay contenedores en estado UNHEALTHY sin resolver
- [ ] No hay migraciones pendientes sin aplicar

## Secuencia de deploy (ejecutar en orden estricto)

### Paso 1: Build
```bash
docker compose build --no-cache
```
Esperado: `Build complete` sin errores.
Si falla: NO continuar. Reportar error y parar.

### Paso 2: Up
```bash
docker compose up -d
```
Esperar 30 segundos para que todos los servicios arranquen.

### Paso 3: Estado de contenedores
```bash
docker ps
```
Verificar que TODOS los servicios están `Up` o `Up (healthy)`.
Si alguno está `Restarting` o `Exiting`: NO continuar. Ver logs con `docker logs <container>`.

### Paso 4: Migraciones
```bash
docker compose exec api alembic upgrade head
```
Esperado: `Running upgrade ... done` sin errores.
Si falla: NO continuar. Revisar archivos de migración.

### Paso 5: Health check
```bash
curl -s http://localhost:8000/health
```
Esperado: `{"status": "ok"}` con 200.

### Paso 6: Ready check
```bash
curl -s http://localhost:8000/ready
```
Esperado: `{"status": "ready", "db": "ok", "redis": "ok"}` con 200.
Si falla: identificar cuál servicio no está listo (DB o Redis).

### Paso 7: Test inbound sintético
```bash
curl -s -X POST http://localhost:8000/api/test/process-message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: salesbot-dev-key-2024" \
  -d '{"tenant_slug": "vitaclinica", "channel": "whatsapp", "sender_phone": "+595981000001", "message_text": "Hola, cuanto cuesta el blanqueamiento?"}'
```
Esperado:
- Response generada (no vacía)
- No contiene "error" en el cuerpo
- `intent` = `pricing_request`

### Paso 8: Verificar worker
```bash
docker logs salesbot_worker --tail=20
```
Verificar que el worker está procesando jobs y no tiene errores repetitivos.

## Formato de reporte

```
=== STAGING DEPLOY REPORT ===
Fecha: [fecha]
Commit: [git hash]

Build: PASS / FAIL
Contenedores up: PASS / FAIL — [detalle]
Migraciones: PASS / FAIL
Health: PASS / FAIL
Ready: PASS / FAIL
Inbound test: PASS / FAIL — [respuesta recibida]
Worker: HEALTHY / UNHEALTHY

RESULTADO: DEPLOY_OK / DEPLOY_FAILED
Próximo paso: [acción recomendada]
```

## Reglas
- Si cualquier paso falla antes del Paso 7: NO marcar como deploy exitoso
- Si el inbound test falla: es un BLOCKER
- Si el worker está UNHEALTHY: es un WARNING (no blocker de deploy, pero registrar)
- Guardar el reporte en: `DEPLOY_LOG.md`
