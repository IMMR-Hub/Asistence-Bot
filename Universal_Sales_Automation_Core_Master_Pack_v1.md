# UNIVERSAL SALES AUTOMATION CORE — MASTER PACK v1.0 (COMPACT)
Propósito: archivo único, compacto y cargable en IAs con límites de contexto. Resume y unifica 9 documentos operativos: blueprint, módulos, roadmap, prompt maestro, tenant config, testing/demo, sales, onboarding, deployment y operations.

---
## 1. MASTER BLUEPRINT

### 1.1 Objetivo
Construir un sistema base multi-tenant, modular y config-driven para automatizar WhatsApp y email, clasificar leads, responder cuando sea seguro, escalar a humano cuando corresponda, registrar todo en CRM y ejecutar follow-ups. Debe servir para múltiples rubros sin tocar el core.

### 1.2 No negociables
1. El core no se modifica por cliente.
2. Toda personalización vive en tenant config, prompts, conocimiento y módulos activables.
3. Adapters de canal no contienen lógica de negocio.
4. Nada hardcodeado por cliente.
5. Todo evento importante debe auditarse.
6. Si falta contexto, el sistema no inventa.
7. Si el sistema duda, escala.
8. Multi-tenant desde día 1.
9. Salidas estructuradas y tipadas.
10. Docker Compose obligatorio.

### 1.3 Alcance v1
Incluye:
- WhatsApp inbound/outbound
- Email inbound/outbound
- Clasificación
- Extracción de entidades
- Respuesta automática
- Escalación humana
- CRM interno
- Follow-up automático
- Multi-tenant
- Configuración por cliente
- API administrativa mínima
- Worker background
- Docker Compose
- Tests críticos

No incluye v1:
- panel frontend completo
- campañas redes
- voz telefónica
- analytics visual avanzados
- pagos
- calendarización compleja multi-sucursal
- fine-tuning de modelos

### 1.4 Arquitectura
- Python 3.11
- FastAPI
- PostgreSQL
- Redis
- RQ
- SQLAlchemy
- Alembic
- Pydantic v2
- Docker Compose
- Inferencia desacoplada (API externa al inicio; migrable a inferencia propia)

### 1.5 Componentes principales
Entrada:
- Webhook WhatsApp
- Webhook Email

Core:
- inbound_router
- intent_classifier
- entity_extractor
- knowledge_resolver
- response_orchestrator
- crm_writer
- follow_up_engine
- human_escalation
- audit_logger
- tenant_config_manager

Persistencia:
- PostgreSQL

Background:
- Redis + RQ Worker

### 1.6 Modelos DB
- Tenant
- TenantConfig
- Contact
- Lead
- Conversation
- Message
- LeadClassification
- FollowUpJob
- Escalation
- AuditEvent

### 1.7 Flujo end-to-end
1. llega inbound
2. se normaliza
3. se audita
4. se carga tenant config
5. se clasifica
6. se extraen entidades
7. se hace upsert CRM
8. se resuelve conocimiento
9. se decide responder o escalar
10. se envía respuesta o se crea escalación
11. se programa follow-up
12. se audita resultado

### 1.8 Reglas de respuesta
Responder solo si:
- confidence >= threshold
- no cae en reglas always_escalate
- hay conocimiento suficiente
- policy del tenant lo permite

Escalar si:
- confidence baja
- customer requests human
- complaint
- urgencia/sensible
- falta conocimiento crítico
- lead caliente según policy del tenant

### 1.9 Definition of Done
- docker compose up -d funciona
- migrations funcionan
- /health responde
- /ready responde
- create tenant/config funciona
- inbound procesa end-to-end
- persiste lead/contact/conversation/message/classification/audit
- responde o escala correctamente
- follow-up se programa
- tests mínimos pasan
- README sirve

---
## 2. MODULE SPECS (COMPACT)

### 2.1 Reglas globales de módulos
- responsabilidad única
- tipado estricto
- dependencias inyectables
- sin lógica hardcodeada por cliente
- logs con tenant_id/message_id/conversation_id cuando existan
- errores estructurados
- nada sensible en logs

### 2.2 inbound_router
Hace:
- recibe payload canal
- valida
- enruta a adapter
- obtiene NormalizedInboundMessage
- dispara orchestration
No hace:
- clasificar
- responder
- decidir escalación

Input:
- channel, payload, headers
Output:
- NormalizedInboundMessage

### 2.3 intent_classifier
Hace:
- usa LLM
- aplica overrides por tenant
- devuelve intent, temperature, urgency, confidence, summary, entities
No hace:
- responder
- escribir DB
Reglas:
- salida JSON estricta
- si salida inválida, retry corto y luego unknown/low confidence

### 2.4 entity_extractor
Hace:
- extraer customer_name, product/service_interest, budget_hint, location_hint, preferred_contact_time, language
No inventa datos.
Null si no encuentra.

### 2.5 knowledge_resolver
Hace:
- cargar tenant config activa
- devolver FAQ, snippets, pricing policy, horarios, tono, firma, etc.
No genera respuesta final.

### 2.6 response_orchestrator
Hace:
- decidir respond vs escalate
- invocar response_service si corresponde
- preparar follow-up
No envía directamente ni persiste por sí solo.

### 2.7 crm_writer
Hace:
- upsert Contact
- upsert Lead
- create/update Conversation
- persist Message
- persist LeadClassification
Reglas:
- idempotencia por provider_message_id si existe

### 2.8 follow_up_engine
Hace:
- schedule jobs
- cancel jobs
- execute follow-ups
Reglas:
- no duplicar jobs
- cancelar si el lead responde o si se escaló
- respetar horarios si policy lo exige

### 2.9 human_escalation
Hace:
- create escalation
- marcar conversación escalada
- preparar fallback message
Siempre con reason + summary + contexto suficiente.

### 2.10 audit_logger
Hace:
- persistir eventos clave
Tipos mínimos:
- inbound_received
- inbound_normalized
- tenant_config_loaded
- classification_completed
- extraction_completed
- crm_upsert_completed
- response_decision_made
- response_sent
- escalation_created
- follow_up_scheduled
- provider_error
- unexpected_error

### 2.11 tenant_config_manager
Hace:
- resolver tenant
- cargar config activa
- validar schema
- exponer config tipada
Si falta config válida, bloquear autopilot.

### 2.12 whatsapp_adapter
Hace:
- validar webhook
- normalizar payload
- enviar outbound
No hace negocio.

### 2.13 email_adapter
Hace:
- normalizar inbound email
- enviar outbound email
No hace negocio.

### 2.14 llm_service
Hace:
- classify
- extract
- generate_response
- generate_follow_up
Debe estar desacoplado del proveedor.

### 2.15 orchestration_service
Coordina pipeline completo end-to-end.

---
## 3. ROADMAP DE CONSTRUCCIÓN

### Fase 0 — Repo base
Crear:
- estructura carpetas
- main.py
- core config/logging/exceptions
- Dockerfile, docker-compose, .env.example, README, alembic.ini
Checkpoint: FastAPI arranca y /health responde.

### Fase 1 — Infra base
- config.py
- logging.py
- exceptions.py
- security.py
- constants.py
Checkpoint: startup limpio y logger funcionando.

### Fase 2 — DB y modelos
Orden:
1. Tenant
2. TenantConfig
3. Contact
4. Lead
5. Conversation
6. Message
7. LeadClassification
8. FollowUpJob
9. Escalation
10. AuditEvent
Más:
- base.py
- session.py
- Alembic
Checkpoint: migrations OK.

### Fase 3 — Schemas
Crear contracts:
- NormalizedInboundMessage
- ClassificationResult
- EntityExtractionResult
- ResponseDecision
- TenantConfigSchema
Checkpoint: validación fuerte.

### Fase 4 — Repositorios
Crear todos los repos según modelo.
Checkpoint: persistencia vía repositorios.

### Fase 5 — Servicios base
Orden:
- tenant_config_service
- audit_service
- llm_service
- knowledge_service
- classification_service
- extraction_service
- lead_service
- escalation_service
- follow_up_service
- response_service
Checkpoint: servicios testeables en aislamiento.

### Fase 6 — Módulos del core
Orden:
- tenant_config_manager
- audit_logger
- intent_classifier
- entity_extractor
- knowledge_resolver
- crm_writer
- human_escalation
- response_orchestrator
- follow_up_engine
- inbound_router
Checkpoint: procesa NormalizedInboundMessage completo.

### Fase 7 — Adapters de canal
WhatsApp y Email, mínimo 1 provider real por canal.
Checkpoint: parse inbound + send outbound.

### Fase 8 — Orchestration
Implementar flujo end-to-end.
Checkpoint: mensaje sintético genera respuesta o escalación y escribe todo.

### Fase 9 — Worker y jobs
- worker.py
- jobs.py
Checkpoint: follow-up schedule/execute.

### Fase 10 — API
Routers:
- health
- tenants
- webhooks_whatsapp
- webhooks_email
- leads
- conversations
- escalations
- internal_test

### Fase 11 — Tests
- unit
- integration
- e2e
No seguir sin tests críticos.

### Fase 12 — Docker y README
Compose, env, README funcional.

### Fase 13 — Tenant de prueba
Ejecutar tenant real (Vitaclinica u otro simple) + demo.

### Fase 14 — Hardening inicial
- rate limiting básico
- retries controlados
- observabilidad mínima
- sanitización
- timeout policies

---
## 4. PROMPT MAESTRO PARA IA EJECUTORA

Usa esto como prompt base para Claude Code / Codex:

Actúa como un principal/staff software engineer con experiencia en sistemas multi-tenant, FastAPI, PostgreSQL, Redis, RQ, LLM orchestration y arquitecturas modulares config-driven.

Tu tarea es construir un repositorio completo runnable a partir de este archivo maestro.

Reglas:
1. No resumas.
2. No simplifiques arquitectura.
3. No propongas alternativas.
4. No reemplaces tecnologías.
5. No cambies el diseño multi-tenant config-driven.
6. No hardcodees reglas de negocio por cliente.
7. No dejes pseudocódigo, TODOs, stubs ni mocks en rutas críticas.
8. No mezcles adapters con negocio.
9. No mezcles repositorios con orquestación.
10. No avances de fase sin completar la anterior.
11. Si falta una decisión menor, elige la opción más simple, robusta y compatible con producción.
12. El resultado final debe correr con docker compose.

Entregables:
- repo runnable
- Dockerfile
- docker-compose.yml
- Alembic con migraciones iniciales
- FastAPI app completa
- modelos SQLAlchemy
- schemas Pydantic v2
- repositorios
- servicios
- módulos core
- adapters WhatsApp y email
- worker RQ
- tests unitarios, integración y e2e mínimos
- .env.example
- README

Criterio de finalización:
No des por terminado el trabajo hasta que:
- todos los archivos existan
- docker compose arranque
- migraciones funcionen
- /health responda
- /ready responda
- exista al menos un test por flujo crítico
- el README permita levantar el sistema desde cero

Modo de respuesta:
- escribe archivos directamente
- no expliques teoría
- avanza por lotes coherentes
- al final de cada bloque entrega:
  1. archivos creados/modificados
  2. comandos para correr/verificar
  3. qué falta del siguiente bloque

Orden obligatorio:
1. estructura y config base
2. DB y modelos
3. migraciones
4. schemas
5. repos
6. services
7. modules
8. adapters
9. orchestration
10. worker
11. API
12. tests
13. docker compose
14. README

Si por límite de contexto no puedes entregar todo en un solo bloque, continúa automáticamente en el siguiente bloque hasta completar el repositorio entero.

---
## 5. TENANT CONFIG STANDARD

### 5.1 Principio
Toda personalización debe vivir aquí. Si para un cliente hay que tocar el core, el config está mal o incompleto.

### 5.2 Estructura recomendada
```json
{
  "tenant_identity": {},
  "channels": {},
  "modules": {},
  "brand": {},
  "business_hours": {},
  "knowledge": {},
  "services_or_products": [],
  "classification": {},
  "escalation": {},
  "follow_up": {},
  "response_policy": {},
  "crm": {},
  "calendar": {},
  "notifications": {},
  "constraints": {},
  "metadata": {}
}
```

### 5.3 Campos clave por bloque
- tenant_identity: tenant_slug, business_name, timezone, default_language, industry_tag, country, city, currency, address
- channels: enabled_channels, default_reply_channel
- modules: enabled_modules
- brand: tone, signature_text, response_style_rules, forbidden_phrases
- business_hours: schedule, after_hours_policy
- knowledge: faq_entries, knowledge_snippets, pricing_policy, location_policy, booking_policy
- services_or_products: name, category, price_from, currency, description, bookable, requires_evaluation, tags
- classification: hot_keywords, warm_keywords, human_request_keywords, emergency_keywords, intent aliases
- escalation: confidence_threshold, always_escalate_x, targets, fallback_messages
- follow_up: rules con trigger, delay, channel, template, cancel_if_reply, respect_hours
- response_policy: allow_autonomous_response, max_length, allowed_languages, forbidden_topics, safe_fallback
- crm: default_lead_status, priority, tags_enabled
- calendar: enabled, mode, booking_requires_confirmation
- notifications: hot lead/escalation notifications
- constraints: never_diagnose, never_prescribe, never_invent_price, etc.
- metadata: version, created_by, notes

### 5.4 Ejemplo mínimo — Vitaclinica
```json
{
  "tenant_identity": {
    "tenant_slug": "vitaclinica",
    "business_name": "Vitaclinica Odontología",
    "timezone": "America/Asuncion",
    "default_language": "es",
    "industry_tag": "dental_clinic",
    "country": "Paraguay",
    "city": "Asuncion",
    "currency": "PYG",
    "physical_address": "Prof. Emiliano Gómez Rios 988, Asunción"
  },
  "channels": {
    "enabled_channels": ["whatsapp", "email"],
    "default_reply_channel": "whatsapp"
  },
  "brand": {
    "tone": "profesional cercano claro",
    "signature_text": "Equipo Vitaclinica 🦷",
    "response_style_rules": [
      "responder corto y claro",
      "no sonar robotico",
      "invitar a agendar una cita"
    ]
  },
  "knowledge": {
    "faq_entries": [
      {"key": "ubicacion", "question_aliases": ["donde estan","direccion"], "answer": "Estamos en Prof. Emiliano Gómez Rios 988, Asunción."},
      {"key": "horario", "question_aliases": ["horario","atienden hoy"], "answer": "Atendemos de lunes a viernes de 09:00 a 20:00 y sábados de 09:00 a 12:00."}
    ],
    "pricing_policy": {
      "mode": "from_price_with_evaluation",
      "message_if_uncertain": "El precio exacto depende de una evaluación personalizada."
    }
  },
  "services_or_products": [
    {"name":"Consulta y evaluación","category":"consulta","price_from":50000,"price_currency":"PYG","bookable":true,"requires_evaluation":false,"tags":["consulta","chequeo"]},
    {"name":"Blanqueamiento dental","category":"estetica","price_from":700000,"price_currency":"PYG","bookable":true,"requires_evaluation":true,"tags":["blanqueamiento","estetica"]}
  ],
  "classification": {
    "hot_keywords": ["precio","turno","hoy","agendar"],
    "human_request_keywords": ["persona","humano","asesor"],
    "emergency_keywords": ["dolor","hinchazon","sangrado","urgencia"]
  },
  "escalation": {
    "rules": {
      "confidence_threshold": 0.72,
      "always_escalate_intents": ["complaint"],
      "always_escalate_keywords": ["dolor","urgencia","reclamo"],
      "always_escalate_hot_leads": true,
      "always_escalate_if_customer_requests_human": true
    },
    "targets": {
      "level_1":"Recepción / Agenda",
      "level_2":"Odontólogo",
      "level_3":"Dirección"
    }
  },
  "follow_up": {
    "rules": [
      {
        "rule_key":"warm_lead_no_reply",
        "enabled":true,
        "trigger_type":"no_response",
        "delay_minutes":120,
        "channel":"same_as_origin",
        "message_template":"Hola 😊 ¿Quieres que te ayudemos a agendar tu consulta?",
        "cancel_if_reply":true,
        "cancel_if_escalated":true,
        "respect_business_hours":true
      }
    ]
  },
  "response_policy": {
    "allow_autonomous_response": true,
    "max_response_length": 450,
    "always_offer_next_step": true,
    "allowed_languages": ["es"],
    "forbidden_topics": ["diagnostico medico","receta de medicamentos"],
    "safe_fallback_message": "Para darte una respuesta correcta, necesito derivar tu consulta a una persona del equipo."
  },
  "constraints": {
    "never_diagnose": true,
    "never_prescribe": true,
    "never_guarantee_results": true,
    "never_confirm_unverified_availability": true,
    "never_invent_price": true
  },
  "metadata": {"config_version":1,"created_by":"system","notes":"Configuración inicial demo"}
}
```

---
## 6. TESTING PACK + DEMO PACK

### 6.1 Capas de testing
- A: smoke tests
- B: functional tests
- C: conversation tests
- D: edge cases
- E: multi-tenant isolation
- F: demo scenarios

### 6.2 Smoke tests
- /health 200
- /ready 200
- DB OK
- Redis OK
- worker activo
- provider LLM accesible
- tenant config cargable
- migraciones aplicadas

### 6.3 Conversation test template
```json
{
  "case_id": "VITA_001",
  "tenant": "vitaclinica",
  "channel": "whatsapp",
  "user_message": "Hola, cuánto cuesta el blanqueamiento?",
  "expected_intent": "pricing_request",
  "expected_temperature": "hot",
  "expected_action": "respond",
  "expected_entities": {
    "product_or_service_interest": "blanqueamiento dental",
    "language": "es"
  },
  "must_create_follow_up": true,
  "must_escalate": false,
  "must_not_do": [
    "inventar precio distinto al configurado",
    "dar diagnóstico"
  ]
}
```

### 6.4 Casos Vitaclinica mínimos
1. precio blanqueamiento → responde + CTA
2. “quiero mejorar mi sonrisa…” → responde + CTA evaluación
3. chequeo general → responde + CTA
4. dolor fuerte + hinchazón → escala
5. reclamo → escala
6. “quiero hablar con una persona” → escala
7. ubicación → responde FAQ
8. horario → responde FAQ
9. ortodoncia precio → responde “desde” o evaluación
10. “hola” → saludo corto

### 6.5 Casos borde
- mensaje vacío
- audio mal transcrito
- múltiples intenciones
- idioma distinto
- cliente agresivo
- prompt injection

### 6.6 Demo de 5 minutos
1. FAQ simple
2. lead caliente
3. cliente indeciso
4. urgencia escalada
5. mostrar CRM / lead guardado / follow-up o escalación

Guion:
“No es un chatbot. Es un sistema que responde, clasifica, guarda, sigue y deriva cuando hace falta.”

---
## 7. SALES PACK

### 7.1 Qué vendes
No vendes:
- chatbot
- automatización
- software

Sí vendes:
“Sistema que convierte mensajes en oportunidades, evita pérdidas por demora y organiza la atención comercial sin contratar más personal.”

### 7.2 Paquetes
#### STARTER
- hasta 50 conversaciones/día
- WhatsApp + email
- respuestas automáticas
- clasificación básica
- CRM básico
- follow-ups simples
- escalación
Precio:
- USD 197/mes
- USD 175/mes anual
- Setup USD 300

#### GROWTH
Todo lo anterior +:
- hasta 150 conversaciones/día
- clasificación avanzada
- follow-ups más inteligentes
- priorización leads calientes
- mejor personalización
Precio:
- USD 497/mes
- USD 375/mes anual
- Setup USD 700

#### PRO
Todo lo anterior +:
- 300+ conversaciones/día
- múltiples flujos
- automatización más compleja
- reporting operativo básico
- soporte prioritario
Precio:
- USD 597/mes
- USD 450/mes anual
- Setup USD 1.500+

#### CUSTOM
- desde USD 1.000/mes

### 7.3 Upsells
- Agenda automática: setup USD 100–300 / mensual USD 30–80
- CRM avanzado: setup USD 200–500 / mensual USD 50–150
- Voz IA: setup USD 300–800 / mensual USD 150–400
- Reactivación: setup USD 200–500 / mensual USD 100–300
- Redes con IA: mensual USD 200–500
- Landing/web: setup USD 300–800
- Dashboard: setup USD 200–500 / mensual USD 50–100

### 7.4 Bundle recomendado clínica
Growth + agenda + redes
≈ USD 847/mes

### 7.5 Objeciones típicas
- “ya tengo secretaria” → esto no compite, le quita lo repetitivo
- “no quiero robot” → escala a humano cuando corresponde
- “está caro” → se paga con pocas conversiones
- “quiero probar” → piloto controlado

### 7.6 Oferta piloto
- 30 días
- alcance controlado
- setup reducido
- métrica clara

---
## 8. ONBOARDING PACK

### 8.1 Flujo
1. cliente acepta propuesta/piloto
2. enviar formulario
3. recibir datos
4. detectar huecos
5. resolver dudas
6. armar tenant config v1
7. test interno
8. demo/piloto
9. ajustar
10. activar

### 8.2 Datos obligatorios
#### Identidad
- nombre negocio
- rubro
- dirección oficial
- ciudad/país
- horario
- idioma
- moneda
- WhatsApp
- email

#### Servicios/productos
- qué vende
- top 5 más importantes
- top 5 más preguntados
- precios desde
- qué requiere evaluación/cotización
- qué no responder sin validación

#### FAQs
- mínimo 10 preguntas frecuentes
- si no las tienen, guiar por categorías

#### Tono
- formalidad
- uso de emojis
- CTA sí/no
- frases prohibidas

#### Escalación
- cuándo escalar
- quién recibe
- por qué canal
- mensaje de derivación

#### Seguimiento
- si quieren follow-up
- a cuánto tiempo
- cuántos máximos
- mensaje de seguimiento
- horarios

### 8.3 Regla
El onboarding termina solo cuando puedes crear el tenant_config y probarlo con seguridad.

---
## 9A. DEPLOYMENT PACK

### 9A.1 Arquitectura inicial recomendada
VPS principal:
- FastAPI
- PostgreSQL
- Redis
- RQ Worker
- Nginx
- monitoreo mínimo
- backups

LLM:
- API externa al inicio
- migrable luego a inferencia propia

### 9A.2 Ambientes
- dev
- staging
- prod

### 9A.3 VPS inicial recomendado
- 4 vCPU
- 8 GB RAM
- 80–160 GB SSD
- Ubuntu LTS

### 9A.4 Host base
- docker
- docker compose plugin
- ufw
- fail2ban
- nginx
- git
- curl
- htop
- cron

### 9A.5 Estructura en servidor
/opt/universal-sales-core/
- repo/
- env/
- backups/
- logs/
- nginx/
- scripts/

### 9A.6 Servicios mínimos compose
- api
- worker
- db
- redis
- nginx

### 9A.7 Variables env mínimas
- APP_ENV
- APP_PORT
- DATABASE_URL
- REDIS_URL
- RQ_QUEUE_NAME
- LLM_PROVIDER
- LLM_API_BASE
- LLM_API_KEY
- OLLAMA_BASE_URL (future/optional)
- WHATSAPP_* tokens
- GMAIL_* or SMTP_*
- DEFAULT_TIMEZONE
- LOG_LEVEL
- SECRET_KEY

### 9A.8 Nginx
- HTTP→HTTPS
- TLS termination
- proxy a API
- paths públicos mínimos:
  - /health
  - /ready
  - /webhooks/whatsapp/inbound
  - /webhooks/email/inbound
  - /api/*

### 9A.9 Backups
- backup DB diario
- retención 7–14 días mínimo
- probar restore

### 9A.10 First deploy
1. preparar VPS
2. instalar Docker/Nginx
3. clonar repo
4. crear .env
5. docker compose up -d
6. correr migraciones
7. validar /health y /ready
8. crear tenant demo
9. cargar config
10. simular inbound

### 9A.11 Reglas críticas
- no exponer DB/Redis públicamente
- no secrets hardcodeados
- restart policy
- TLS obligatorio en prod
- rollback mínimo
- health checks obligatorios

---
## 9B. OPERATIONS PACK

### 9B.1 Capas operativas
- infraestructura
- aplicación
- tenant behavior
- soporte al cliente
- mejora continua

### 9B.2 Roles
- Operador técnico
- Implementador/configurador
- Responsable de cliente
- Responsable de negocio del cliente

### 9B.3 Estados
- verde
- amarillo
- rojo

### 9B.4 Rutina diaria
Revisar:
- /health
- /ready
- contenedores
- logs
- jobs fallidos
- CPU/RAM/disco
- follow-ups pendientes
- escalaciones

### 9B.5 Rutina semanal
- volumen por tenant
- errores por tenant
- % escalaciones
- respuestas fallidas
- backups
- costos
- nuevas FAQs
- cambios del negocio

### 9B.6 Rutina mensual
- performance por cliente
- rentabilidad por cliente
- oportunidades de upsell
- deuda técnica/operativa
- incidentes del mes

### 9B.7 Tipos de ticket
- incidente
- ajuste
- mejora
- cambio mayor
- soporte informativo

### 9B.8 Prioridades
- P1 crítico
- P2 alto
- P3 medio
- P4 bajo

### 9B.9 Gestión de incidentes
1. detectar
2. confirmar impacto
3. clasificar severidad
4. contener
5. restaurar servicio
6. investigar causa raíz
7. corregir
8. documentar

### 9B.10 Operación de tenant configs
- versionar
- validar schema
- probar antes de activar
- no editar a ciegas en prod

### 9B.11 Gestión de follow-ups
- revisar si convierten
- pausar si generan spam/quejas
- respetar horarios
- cancelar si ya se respondió/escaló

### 9B.12 Gestión de escalaciones
Revisar:
- volumen
- calidad
- si faltan o sobran
- targets correctos

### 9B.13 Costos
Controlar:
- VPS
- LLM
- canal
- costo por cliente
- margen real

### 9B.14 Regla operativa final
No improvisar soporte, cambios ni incidentes. Priorizar estabilidad, trazabilidad y mejora continua.

---
## 10. ANEXO — ESTRUCTURA DE REPO RECOMENDADA

```txt
app/
  main.py
  core/
    config.py
    logging.py
    security.py
    exceptions.py
    constants.py
  api/routes/
    health.py
    tenants.py
    webhooks_whatsapp.py
    webhooks_email.py
    leads.py
    conversations.py
    escalations.py
    internal_test.py
  db/
    base.py
    session.py
    models/
    repositories/
  schemas/
  services/
  modules/
  channels/
    whatsapp/
    email/
  workers/
  tests/
    unit/
    integration/
    e2e/
Dockerfile
docker-compose.yml
alembic.ini
.env.example
README.md
```

---
## 11. ANEXO — CHECKLIST EJECUTIVO PARA IA O EQUIPO

### Antes de construir
- leer secciones 1–5
- congelar stack
- respetar arquitectura modular multi-tenant

### Antes de demo
- tenant config cargado
- FAQs correctas
- precios desde validados
- rutas de escalación definidas
- casos demo listos

### Antes de producción
- deploy pack OK
- operations pack OK
- backups OK
- health/ready OK
- webhook test OK
- rollback mínimo OK

---
## 12. INSTRUCCIÓN FINAL

Usa este archivo como contrato técnico-comercial-operativo comprimido.
Si necesitas más detalle, expande solo la sección necesaria.
No cambies:
- arquitectura
- separación por capas
- estrategia multi-tenant config-driven
- idea central de core reusable + módulos plug-and-play
