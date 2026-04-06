# SKILL: repo-auditor

## Propósito
Auditar el estado real del repositorio al inicio de cada sesión. No opina. No propone cambios aún. Solo detecta y reporta.

## Fuentes de verdad obligatorias
Antes de auditar, leer:
1. `Universal_Sales_Automation_Core_Master_Pack_v1.md` — blueprint y contratos
2. `AUDITORIA_CORRECTIVA.md` — hallazgos pendientes
3. `tenants/vitaclinica-config.json` — config activa del tenant

## Checklist de auditoría (ejecutar en orden)

### 1. Contratos de intents
- Listar todos los intents definidos en `app/modules/intent_classifier/classifier.py`
- Listar todos los intents usados en `app/services/message_processor.py`
- Listar todos los intents en las reglas de escalación del tenant config
- Comparar: ¿hay intents usados que no están definidos? ¿hay definidos que nunca se usan?
- Reportar: ALIGNED / MISMATCHED (con lista de diferencias)

### 2. Contratos de módulos
- Verificar que cada módulo en `app/modules/` tiene: entrada tipada, salida tipada, sin lógica hardcodeada por cliente
- Buscar strings literales de clientes en módulos (ej: "vitaclinica", "odontología")
- Reportar: OK / VIOLATION (con archivo y línea)

### 3. Worker health
- Correr: `docker ps` y verificar estado del contenedor `salesbot_worker`
- Si UNHEALTHY: reportar estado actual + logs últimas 20 líneas
- Reportar: HEALTHY / UNHEALTHY / NOT_RUNNING

### 4. TODOs en rutas críticas
- Buscar `TODO`, `FIXME`, `pass`, `raise NotImplementedError`, `...` en:
  - `app/modules/`
  - `app/services/`
  - `app/channels/`
- Reportar: CLEAN / FOUND (con lista de archivos y líneas)

### 5. Imports rotos
- Correr: `python -c "from app.main import app"` dentro del contenedor api
- Reportar: OK / BROKEN (con error)

### 6. Tests existentes
- Listar todos los archivos en `app/tests/`
- Contar: unit / integration / e2e
- Reportar: conteo actual vs mínimo requerido (20 conversation + 5 edge + 3 multi-tenant)

### 7. Variables de entorno
- Verificar que docker-compose.yml tiene todas las vars del `.env.example`
- Verificar que ningún secret está hardcodeado en código fuente
- Reportar: OK / MISSING_VARS / HARDCODED_SECRETS

## Formato de salida

```
=== REPO AUDIT REPORT ===
Fecha: [fecha]
Estado general: VERDE / AMARILLO / ROJO

1. Contratos de intents: [estado] — [detalle]
2. Contratos de módulos: [estado] — [detalle]
3. Worker health: [estado] — [detalle]
4. TODOs críticos: [estado] — [detalle]
5. Imports: [estado] — [detalle]
6. Tests: [X unit / Y integration / Z e2e]
7. Env vars: [estado] — [detalle]

BLOCKERS (no continuar sin resolver):
- [lista]

WARNINGS (resolver en este sprint):
- [lista]
```

## Reglas
- No modificar nada durante la auditoría
- Si algo no se puede verificar, marcarlo como UNKNOWN con razón
- Completar toda la auditoría antes de reportar
- Si hay BLOCKERS, pausar y reportar antes de continuar
