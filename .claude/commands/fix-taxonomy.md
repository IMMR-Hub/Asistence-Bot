# /fix-taxonomy

Corrige la taxonomía de intents del sistema para alinear clasificador, orquestador, DB y reglas de negocio.

## Qué hace este comando

1. **Audita** todos los intents definidos vs usados en el sistema
2. **Corrige** el enum oficial de intents en `classifier.py`
3. **Agrega** `clinical_urgency` como dimensión separada de `complaint`
4. **Alinea** las reglas de escalación del tenant config
5. **Corre** tests para verificar que todo está alineado

## Intents oficiales después de la corrección

```python
class MessageIntent(str, Enum):
    PRODUCT_INQUIRY = "product_inquiry"
    PRICING_REQUEST = "pricing_request"
    APPOINTMENT_REQUEST = "appointment_request"
    COMPLAINT = "complaint"              # Reclamo comercial
    SUPPORT_REQUEST = "support_request"
    FOLLOW_UP_REPLY = "follow_up_reply"
    UNKNOWN = "unknown"
```

## Dimensiones adicionales (NO intents separados)

```python
class MessageFlags(BaseModel):
    customer_requests_human: bool = False   # Reemplaza "human_request" intent
    clinical_urgency: bool = False          # Dolor, sangrado, urgencia médica
    urgency_level: str = "normal"           # normal | high | critical
```

## Regla de clasificación para casos médicos

Si el mensaje contiene palabras de urgencia clínica (`dolor`, `sangrado`, `hinchazón`, `urgencia`, `emergencia`):
- `intent` = `support_request` (NO `complaint`)
- `clinical_urgency` = `True`
- `urgency_level` = `high` o `critical`
- Pipeline de escalación debe usarse por `clinical_urgency = True`, no por intent

## Archivos a modificar

- `app/modules/intent_classifier/classifier.py` — enum + prompt
- `app/schemas/message.py` o `app/schemas/classification.py` — agregar MessageFlags
- `app/services/message_processor.py` — leer `clinical_urgency` para decisión de escalación
- `app/modules/human_escalation/escalation.py` — trigger por `clinical_urgency`
- Tests: `app/tests/` — agregar test de urgencia clínica

## Criterio de cierre

- [ ] `dolor de muela` → `support_request` + `clinical_urgency=True` → escala
- [ ] `estoy enojado con el servicio` → `complaint` + `clinical_urgency=False` → escala
- [ ] `quiero hablar con alguien` → cualquier intent + `customer_requests_human=True` → escala
- [ ] Todos los intents en el enum son los únicos que puede devolver el clasificador
- [ ] Tests pasan

Usar skill `bugfix-executor` para cada corrección y `strict-code-review` antes de cerrar.
