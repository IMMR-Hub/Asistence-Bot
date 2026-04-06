# SKILL: tenant-config-validator

## Propósito
Validar que una tenant config cumple el schema del Master Pack, no mete lógica en el core, y no rompe restricciones de negocio. Ejecutar antes de activar cualquier tenant config en producción.

## Fuente de verdad
Schema oficial en: `Universal_Sales_Automation_Core_Master_Pack_v1.md` sección 5.

## Validaciones obligatorias

### 1. Campos requeridos
Verificar que existen y no están vacíos:
- `tenant_identity.tenant_slug`
- `tenant_identity.business_name`
- `tenant_identity.timezone`
- `tenant_identity.default_language`
- `channels.enabled_channels` (mínimo 1)
- `brand.tone`
- `escalation.rules.confidence_threshold`
- `response_policy.allow_autonomous_response`
- `response_policy.safe_fallback_message`

### 2. Tipos de datos
- `confidence_threshold`: float entre 0.0 y 1.0
- `enabled_channels`: array de strings válidos (`whatsapp`, `email`)
- `business_hours`: si existe, debe tener `schedule` con días válidos
- `services_or_products`: si existe, cada item debe tener `name`, `price_from`, `price_currency`

### 3. Restricciones de negocio — industria médica/salud
Si `industry_tag` contiene: `dental`, `clinic`, `health`, `medical`, `pharma`:
- Verificar que `constraints.never_diagnose = true`
- Verificar que `constraints.never_prescribe = true`
- Verificar que `constraints.never_guarantee_results = true`
- Verificar que `escalation.rules.always_escalate_keywords` incluye términos de urgencia clínica: `dolor`, `sangrado`, `hinchazón`, `urgencia`
- Verificar que `forbidden_topics` incluye `diagnostico medico` y `receta de medicamentos`

### 4. Verificación de no-hardcoding
- Asegurarse que la config NO hace referencia a módulos del core por nombre
- Asegurarse que la config NO incluye código Python, condicionales de código ni imports
- La personalización debe ser SOLO datos: strings, arrays, booleans, numbers

### 5. Coherencia interna
- Si `calendar.enabled = true`: verificar que `booking_policy` existe
- Si `follow_up.rules` tiene items: verificar que tienen `delay_minutes`, `channel`, `message_template`
- Si `escalation.targets` existe: verificar que tiene al menos `level_1`

### 6. Prueba de carga
- Cargar el JSON en el sistema con: `POST /api/tenants/{slug}/config`
- Verificar respuesta 200
- Correr un mensaje de prueba sintético con tenant config activa
- Verificar que la respuesta usa `business_name` correcto (no de otro tenant)

## Formato de salida

```
=== TENANT CONFIG VALIDATION ===
Tenant: [slug]
Fecha: [fecha]

Campos requeridos: PASS / FAIL — [detalle]
Tipos de datos: PASS / FAIL — [detalle]
Restricciones de negocio: PASS / FAIL — [detalle]
No-hardcoding: PASS / FAIL — [detalle]
Coherencia interna: PASS / FAIL — [detalle]
Prueba de carga: PASS / FAIL — [detalle]

RESULTADO: APPROVED / REJECTED
Razones de rechazo: [si aplica]
```

## Regla final
Una tenant config no se activa en producción hasta tener APPROVED en todas las validaciones.
