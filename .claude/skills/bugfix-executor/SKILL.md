# SKILL: bugfix-executor

## Propósito
Corregir bugs de forma disciplinada: reproducir → localizar → corregir → probar → documentar. No tocar capas no relacionadas al bug.

## Protocolo obligatorio (5 pasos, en orden)

### Paso 1: REPRODUCIR
- Identificar el mensaje de error exacto o el comportamiento incorrecto
- Crear un test mínimo que reproduzca el bug (si no existe)
- Verificar que el test FALLA antes de hacer cualquier cambio
- Si no se puede reproducir: marcar como NEEDS_INVESTIGATION y parar

### Paso 2: LOCALIZAR
- Trazar la ejecución desde el punto de entrada hasta el punto de falla
- Identificar el archivo exacto, función y línea
- Confirmar la causa raíz (no la causa superficial)
- Preguntar: ¿es un síntoma de un problema más profundo? Si sí, documentarlo pero no expandir el scope

### Paso 3: CORREGIR
- Hacer el cambio mínimo necesario para resolver el bug
- No refactorizar mientras se corrige
- No cambiar comportamiento de otros módulos
- No agregar features mientras se corrige
- Si la corrección requiere cambios en múltiples capas: documentar cada cambio y su justificación

### Paso 4: PROBAR
- Correr el test de reproducción — debe PASAR ahora
- Correr tests del módulo afectado — no deben romperse
- Correr smoke test del sistema: `/health` y `/ready`
- Si hay tests de regresión: correrlos
- Si algún test falla: NO cerrar el bug, volver al Paso 3

### Paso 5: DOCUMENTAR
Registrar en el reporte de cierre:
```
BUG: [nombre/descripción]
CAUSA RAÍZ: [qué y por qué]
ARCHIVOS MODIFICADOS: [lista]
CAMBIOS REALIZADOS: [resumen]
TESTS CORRIDOS: [lista y resultado]
ESTADO: FIXED / PARTIALLY_FIXED / BLOCKED
DEUDA TÉCNICA DETECTADA: [si aplica]
```

## Restricciones absolutas
- NUNCA tocar el core (arquitectura, contratos base) para resolver un bug de módulo
- NUNCA agregar lógica hardcodeada por cliente para resolver un bug
- NUNCA cerrar un bug sin test que lo verifique
- NUNCA modificar más de 3 archivos sin justificación documentada

## Bugs prioritarios conocidos (orden de ejecución)
1. Worker unhealthy — ver `docker ps` y logs del contenedor worker
2. Intent taxonomy mismatch — `human_request` vs contrato oficial
3. Clasificación de urgencias clínicas como `complaint`
4. Email adapter — clarificar scope inbound vs outbound
