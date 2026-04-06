# vitaclinica-setup.ps1
# Crea el tenant Vitaclinica via API - SIN TOCAR EL CODIGO DEL CORE
# Para agregar otro cliente en el futuro: copiar este archivo, cambiar los datos, ejecutar. Nada mas.

# Encoding UTF-8 para caracteres en espanol y emojis
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$API_KEY = "salesbot-dev-key-2024"
$BASE_URL = "http://localhost:8000"
$headers = @{
    "x-api-key"    = $API_KEY
    "Content-Type" = "application/json"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Vitaclinica Odontologia - Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# PASO 1: Crear el tenant base
Write-Host "Paso 1: Registrando tenant..." -ForegroundColor Yellow

$tenantBody = @{
    tenant_slug      = "vitaclinica"
    business_name    = "Vitaclinica Odontologia"
    timezone         = "America/Asuncion"
    default_language = "es"
    industry_tag     = "odontologia"
} | ConvertTo-Json

try {
    $tenant = Invoke-RestMethod -Method Post -Uri "$BASE_URL/api/tenants" -Headers $headers -Body $tenantBody
    $TENANT_ID = $tenant.id
    Write-Host "✅ Tenant creado. ID: $TENANT_ID" -ForegroundColor Green
} catch {
    $errMsg = $_.ToString()
    if ($errMsg -like "*already exists*" -or $errMsg -like "*409*") {
        $TENANT_ID = "cd1912d2-73e8-4df4-8c82-d38a7e1976ee"
        Write-Host "⚠️  Tenant ya existe. Usando ID: $TENANT_ID" -ForegroundColor Yellow
    } else {
        Write-Host "❌ Error: $errMsg" -ForegroundColor Red
        exit 1
    }
}

# PASO 2: Cargar la configuracion completa del cliente
Write-Host ""
Write-Host "Paso 2: Cargando configuracion completa..." -ForegroundColor Yellow

$config = @{
    config = @{
        tenant_slug      = "vitaclinica"
        business_name    = "Vitaclinica Odontologia"
        timezone         = "America/Asuncion"
        default_language = "es"
        industry_tag     = "odontologia"
        currency         = "PYG"
        allowed_languages = @("es")
        crm_owner_name   = "Sofia - Recepcionista Vitaclinica"
        signature_text   = "Sofia - Vitaclinica Odontologia"

        enabled_channels = @("whatsapp", "email")
        enabled_modules  = @(
            "inbound_router", "intent_classifier", "entity_extractor",
            "response_orchestrator", "knowledge_resolver", "crm_writer",
            "follow_up_engine", "human_escalation", "audit_logger",
            "whatsapp_adapter", "email_adapter"
        )

        brand_tone = "femenino calido empático amable cercano profesional"

        business_hours = @{
            monday_to_friday = "09:00-20:00"
            saturday         = "09:00-12:00"
            sunday           = "cerrado"
        }

        faq_entries = @(
            @{ question = "donde estan ubicados";         answer = "Estamos en Prof. Emiliano Gomez Rios 988, Asuncion." }
            @{ question = "cual es el horario";           answer = "Lunes a viernes de 09:00 a 20:00 y sabados de 09:00 a 12:00." }
            @{ question = "cuanto cuesta una consulta";   answer = "La evaluacion tiene un costo desde 50.000 Gs." }
            @{ question = "cuanto cuesta el blanqueamiento"; answer = "Desde 700.000 Gs, dependiendo del caso." }
            @{ question = "atienden urgencias";           answer = "Si, podemos ayudarte. Te derivamos ahora mismo para prioridad." }
            @{ question = "como agendo una cita";         answer = "Podemos agendarte ahora mismo. Que dia te queda mejor?" }
            @{ question = "cuanto cuesta la limpieza dental"; answer = "La limpieza dental tiene un costo desde 150.000 Gs." }
            @{ question = "cuanto cuestan las carillas";  answer = "Las carillas dentales tienen un precio desde 1.500.000 Gs." }
            @{ question = "cuanto cuesta el diseno de sonrisa"; answer = "El diseno de sonrisa tiene un costo desde 3.000.000 Gs." }
            @{ question = "cuanto cuesta la ortodoncia";  answer = "La ortodoncia tiene un precio desde 2.500.000 Gs." }
        )

        knowledge_documents = @(
            "SERVICIOS Y PRECIOS de Vitaclinica Odontologia:`nConsulta y evaluacion: desde 50.000 Gs`nLimpieza dental: desde 150.000 Gs`nBlanqueamiento dental: desde 700.000 Gs`nCarillas dentales: desde 1.500.000 Gs`nDiseno de sonrisa: desde 3.000.000 Gs`nOrtodoncia: desde 2.500.000 Gs`nUrgencias odontologicas: desde 100.000 Gs"
            "REGLAS OBLIGATORIAS - LO QUE NUNCA DEBES HACER:`n- NUNCA diagnosticar enfermedades`n- NUNCA recetar medicamentos`n- NUNCA garantizar resultados`n- NUNCA inventar precios no listados`n- NUNCA confirmar tratamientos sin evaluacion`n- Si no sabes: responde exactamente: Para darte una respuesta correcta, te conecto con un profesional ahora mismo."
            "OBJETIVO COMERCIAL:`nSiempre invitar a agendar cita. CTAs a usar: Me encantaria agendarte una cita / Te gustaria venir esta semana? / Que dia te queda mejor? El objetivo principal es que el paciente AGENDE."
            "EMERGENCIAS:`nSi el paciente menciona dolor, infeccion, sangrado o hinchazon -> escalar INMEDIATAMENTE. Responder: Ay, entiendo que es urgente. Te comunicamos ahora mismo con nuestro equipo para atenderte lo antes posible."
            "UBICACION: Prof. Emiliano Gomez Rios 988, Asuncion, Paraguay."
            "PERSONALIDAD:`nSoy la recepcionista virtual de Vitaclinica Odontologia. Soy una mujer amable, empática, cálida y profesional. Trato a cada paciente como si fuera mi amiga. Uso un lenguaje accesible, nunca solemne. Me interesa genuinamente en los pacientes y sus necesidades. Siempre estoy lista para ayudar con una sonrisa. Si me preguntan mi nombre, respondo: Soy Sofia, la recepcionista virtual de Vitaclinica."
            "ESTILO DE COMUNICACION:`nUsa emojis relevantes de forma natural (no en cada oración). Escribe en español correcto. Sé cálida y cercana. IMPORTANTE: Responde como una amiga, no como un bot. Una sola idea por mensaje. No hagas varias preguntas en una oración. No ofrezcas cosas que el paciente no pidió. Escucha primero, propone después. Si pregunta precio, solo da el precio. Si quiere agendar, entonces agendás."
            "FLUJO CONVERSACIONAL:`nNo fuerces la venta. Deja que el paciente lleve la conversación. Ejemplos correctos: Paciente pregunta precio -> Tu respuesta: 'El blanqueamiento cuesta desde 700.000 Gs' (punto). Si el paciente muestra interés o pregunta más, entonces ofreces agendar. Paciente dice 'quiero agendar' -> Tu respuesta: 'Claro! Me encantaría ayudarte. Qué día te vendría mejor?' (una sola pregunta). Nunca digas dos cosas a la vez."
        )

        escalation_rules = @{
            confidence_threshold       = 0.70
            always_escalate_hot_leads  = $false
            always_escalate_complaints = $true
        }

        follow_up_rules = @(
            @{ rule_key = "sin_respuesta_2h";  delay_minutes = 120;  channel = "same_as_origin"; enabled = $true }
            @{ rule_key = "lead_tibio_24h";    delay_minutes = 1440; channel = "same_as_origin"; enabled = $true }
        )

        classification_overrides = @{
            hot_keywords           = @("precio", "turno", "cita", "hoy", "cuanto", "costo", "cuanto sale", "quiero", "necesito")
            human_request_keywords = @("persona", "humano", "asesor", "doctor", "odontologo", "hablar con alguien")
        }
    }
} | ConvertTo-Json -Depth 10

try {
    Invoke-RestMethod -Method Post -Uri "$BASE_URL/api/tenants/$TENANT_ID/configs" -Headers $headers -Body $config | Out-Null
    Write-Host "✅ Configuracion cargada correctamente" -ForegroundColor Green
} catch {
    Write-Host "❌ Error al crear config: $_" -ForegroundColor Red
    exit 1
}

# PASO 3: Prueba automatica con mensaje real
Write-Host ""
Write-Host "Paso 3: Probando con mensajes de prueba..." -ForegroundColor Yellow

$testMessages = @(
    @{ text = "Hola Sofia, cuanto cuesta el blanqueamiento dental?";    desc = "Consulta de precio" }
    @{ text = "Tengo dolor de muela muy fuerte, necesito ayuda urgente";  desc = "Urgencia dental" }
    @{ text = "Me encantaria agendar una cita para esta semana";         desc = "Agendar cita" }
    @{ text = "Quiero hablar con un odontologo, tengo dudas";                  desc = "Solicitud humano" }
)

foreach ($msg in $testMessages) {
    Write-Host ""
    Write-Host "--- Prueba: $($msg.desc) ---" -ForegroundColor Magenta
    Write-Host "Mensaje: $($msg.text)" -ForegroundColor Gray

    $testBody = @{
        tenant_slug   = "vitaclinica"
        channel       = "whatsapp"
        contact_phone = "595981000001"
        contact_name  = "Paciente Test"
        text_content  = $msg.text
    } | ConvertTo-Json

    try {
        $result = Invoke-RestMethod -Method Post -Uri "$BASE_URL/api/test/process-message" -Headers $headers -Body $testBody
        Write-Host "Escalado: $($result.escalated)" -ForegroundColor $(if ($result.escalated) { "Yellow" } else { "Green" })
        if ($result.escalation_reason) {
            Write-Host "Razon: $($result.escalation_reason)" -ForegroundColor Yellow
        }
        if ($result.response_text) {
            Write-Host "Bot: $($result.response_text)" -ForegroundColor Cyan
        }
    } catch {
        Write-Host "Error: $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup Vitaclinica COMPLETADO" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "REGLA DE ORO:" -ForegroundColor Yellow
Write-Host "  Nuevo cliente = copiar este archivo + cambiar datos + ejecutar." -ForegroundColor Yellow
Write-Host "  El core NO se toca. Plug and Play." -ForegroundColor Yellow
Write-Host ""
