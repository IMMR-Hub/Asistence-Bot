# /expand-tests

Genera y ejecuta el suite completo de tests requerido para declarar el sistema demo-ready.

## Qué hace este comando

1. Verifica cuántos tests existen actualmente
2. Genera los tests faltantes hasta completar el mínimo requerido
3. Los ejecuta todos
4. Reporta resultado

## Ejecutar

Usar skill `test-expander` con tenant `vitaclinica`.

Los tests se ejecutan via:
```bash
curl -s -X POST http://localhost:8000/api/test/process-message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: salesbot-dev-key-2024" \
  -d '{"tenant_slug": "vitaclinica", "channel": "whatsapp", "sender_phone": "+595981XXXXXX", "message_text": "..."}'
```

## Criterio de demo-ready

| Categoría | Mínimo | Actual |
|---|---|---|
| Conversation tests (happy path) | 20 | verificar |
| Edge cases | 10 | verificar |
| Multi-tenant isolation | 3 | verificar |
| Provider failure | 3 | verificar |
| Idempotencia | 1 | verificar |

Si `Actual >= Mínimo` en todas las categorías: sistema es DEMO_READY.
Si alguna falla: generar los faltantes y volver a correr.

## Guardar resultados

Guardar el reporte en: `TEST_RESULTS_VITACLINICA.md`
Con fecha, versión del sistema y porcentaje de pass.
