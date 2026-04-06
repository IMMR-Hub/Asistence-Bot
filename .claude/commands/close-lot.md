# /close-lot

Cierra un lote de trabajo de forma disciplinada. Ejecutar al terminar cada sprint o bloque de cambios.

## Qué hace este comando

1. Lista todos los archivos modificados en este lote
2. Corre `strict-code-review` sobre esos archivos
3. Corre tests relevantes al lote
4. Genera el reporte de cierre
5. Marca el lote como DONE o BLOCKED

## Formato de reporte de cierre

```
=== CLOSE LOT REPORT ===
Lote: [nombre descriptivo]
Fecha: [fecha]
Duración: [tiempo estimado]

ARCHIVOS MODIFICADOS:
- [archivo 1] — [qué cambió]
- [archivo 2] — [qué cambió]

TESTS CORRIDOS:
- [test] — PASS / FAIL

CODE REVIEW: APPROVED / REJECTED
BLOCKERs: [lista o "ninguno"]

ESTADO: DONE / BLOCKED
Si BLOCKED: [qué falta para desbloquearlo]

PRÓXIMO LOTE: [nombre del siguiente bloque]
DEUDA TÉCNICA DETECTADA: [si aplica]
```

## Lotes del Sprint 1 (desbloquear demo)

1. `fix-worker` — Reparar RQ Worker
2. `migrate-llm` — Migrar a Together.ai
3. `fix-taxonomy` — Corregir intents y urgencias clínicas

## Lotes del Sprint 2 (corregir contrato técnico)

4. `tenant-isolation-proof` — Probar multi-tenant con 2 tenants
5. `email-adapter-scope` — Documentar y separar inbound/outbound email
6. `contract-audit` — Auditar todos los contratos entre capas

## Lotes del Sprint 3 (piloto real)

7. `expand-tests` — Completar suite de 38 tests
8. `deploy-staging` — Deploy estable con HTTPS
9. `ops-runbook` — Documentar todos los procedimientos operativos

## Regla

Un lote DONE significa:
- Código modificado
- Code review aprobado
- Tests corridos y pasando
- Reporte generado

Un lote BLOCKED significa:
- Se detectó un blocker que requiere una decisión o recurso externo
- Se documenta claramente qué falta
- No se avanza hasta resolver el blocker
