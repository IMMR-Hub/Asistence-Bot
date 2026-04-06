# SKILL: strict-code-review

## Propósito
Revisar cada lote de código antes de cerrarlo. Detectar violaciones de arquitectura, acoplamiento indebido, lógica hardcodeada y deuda operativa. No es opcional — se ejecuta antes de marcar cualquier lote como DONE.

## Checklist de revisión (ejecutar sobre todos los archivos modificados en el lote)

### 1. Principio Plug & Play
- [ ] No hay strings de nombres de clientes hardcodeados (ej: "vitaclinica", "Vitaclinica", "odontología")
- [ ] No hay lógica de negocio específica de cliente en módulos del core
- [ ] Toda personalización viene de tenant config, no de código
- [ ] Si hay un `if tenant_slug == "algo":` → VIOLATION

### 2. Separación de capas
- [ ] Adapters de canal no contienen lógica de clasificación ni decisión de escalación
- [ ] Repositorios no contienen lógica de orquestación
- [ ] Módulos no persisten datos directamente (deben ir vía repositorio)
- [ ] Services no parsean payloads de canal directamente

### 3. Contratos tipados
- [ ] Toda función que cruza capas tiene tipos explícitos (Pydantic v2 o dataclass)
- [ ] No hay `dict` sin tipar cruzando entre módulos
- [ ] No hay `Any` sin justificación documentada
- [ ] Los intents devueltos por el clasificador están dentro del enum oficial

### 4. Manejo de errores
- [ ] No hay `except:` o `except Exception: pass` sin logging
- [ ] Errores de proveedor LLM tienen fallback documentado
- [ ] Errores de DB tienen rollback o manejo explícito
- [ ] No hay `print()` o `logging.debug` con datos sensibles

### 5. Seguridad
- [ ] No hay secrets hardcodeados (tokens, passwords, API keys)
- [ ] No hay datos de clientes en logs (phone numbers, nombres)
- [ ] Los endpoints de API tienen autenticación (`X-API-Key`)
- [ ] El webhook de WhatsApp valida el `verify_token`

### 6. Calidad operativa
- [ ] No hay `TODO`, `FIXME`, `pass`, `raise NotImplementedError` en rutas críticas
- [ ] Funciones críticas tienen docstring mínimo (qué hace, qué devuelve)
- [ ] No hay imports no usados
- [ ] No hay código comentado sin explicación

### 7. Tests
- [ ] El lote incluye o actualiza tests para los cambios realizados
- [ ] Los tests verifican comportamiento, no implementación
- [ ] Los tests pasan antes de cerrar el lote

## Severidades

| Nivel | Descripción | Acción |
|---|---|---|
| BLOCKER | Viola arquitectura o seguridad | No merge, corregir antes |
| WARNING | Deuda técnica o calidad baja | Registrar y planificar corrección |
| INFO | Sugerencia de mejora | Opcional |

## Formato de reporte

```
=== CODE REVIEW REPORT ===
Lote: [nombre del lote]
Archivos revisados: [lista]
Fecha: [fecha]

Plug & Play: PASS / FAIL — [detalle]
Separación de capas: PASS / FAIL — [detalle]
Contratos tipados: PASS / FAIL — [detalle]
Manejo de errores: PASS / FAIL — [detalle]
Seguridad: PASS / FAIL — [detalle]
Calidad operativa: PASS / FAIL — [detalle]
Tests: PASS / FAIL — [detalle]

BLOCKERs: [lista o "ninguno"]
WARNINGs: [lista o "ninguno"]

RESULTADO: APPROVED / REJECTED
```

## Regla final
Un lote no se cierra como DONE si tiene al menos 1 BLOCKER.
