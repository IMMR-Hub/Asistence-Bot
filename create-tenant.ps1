# create-tenant.ps1 - Create first tenant and configuration

param(
    [string]$TenantSlug = "forestal-caaguazu",
    [string]$BusinessName = "Forestal Caaguazu SA",
    [string]$Timezone = "America/Asuncion",
    [string]$Language = "es",
    [string]$ApiKey = ""
)

if ([string]::IsNullOrEmpty($ApiKey)) {
    Write-Host "Enter your API_SECRET_KEY (from .env): " -ForegroundColor Yellow -NoNewline
    $ApiKey = Read-Host -AsSecureString | ConvertFrom-SecureString -AsPlainText
}

Write-Host ""
Write-Host "Creating tenant: $TenantSlug" -ForegroundColor Cyan
Write-Host ""

# Create Tenant
Write-Host "Step 1: Creating tenant..." -ForegroundColor Yellow
$tenantBody = @{
    tenant_slug = $TenantSlug
    business_name = $BusinessName
    timezone = $Timezone
    default_language = $Language
    industry_tag = "forestry"
} | ConvertTo-Json

$response = curl -s -X POST http://localhost:8000/api/tenants `
    -H "Content-Type: application/json" `
    -H "X-API-Key: $ApiKey" `
    -d $tenantBody

$tenant = $response | ConvertFrom-Json
$TenantId = $tenant.id

if ($tenant.id) {
    Write-Host "✅ Tenant created: $TenantId" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to create tenant. Check your API key." -ForegroundColor Red
    Write-Host $response -ForegroundColor Red
    exit 1
}

# Configure Tenant
Write-Host "`nStep 2: Configuring tenant..." -ForegroundColor Yellow
$configBody = @{
    config = @{
        tenant_slug = $TenantSlug
        business_name = $BusinessName
        timezone = $Timezone
        default_language = $Language
        enabled_channels = @("whatsapp", "email")
        enabled_modules = @(
            "inbound_router", "intent_classifier", "entity_extractor",
            "response_orchestrator", "knowledge_resolver", "crm_writer",
            "follow_up_engine", "human_escalation", "audit_logger",
            "whatsapp_adapter", "email_adapter"
        )
        brand_tone = "professional_close_clear"
        business_hours = @{
            monday_to_friday = "08:00-18:00"
            saturday = "08:00-12:00"
            sunday = "closed"
        }
        faq_entries = @(
            @{
                question = "ubicacion"
                answer = "Compartimos ubicación exacta cuando el cliente la solicita."
            },
            @{
                question = "horario"
                answer = "Respondemos dentro del horario comercial y el sistema toma consultas 24/7."
            }
        )
        escalation_rules = @{
            confidence_threshold = 0.72
            always_escalate_hot_leads = $true
            always_escalate_complaints = $true
        }
        follow_up_rules = @(
            @{
                rule_key = "warm_lead_no_reply"
                delay_minutes = 120
                channel = "same_as_origin"
                enabled = $true
            }
        )
        classification_overrides = @{
            hot_keywords = @("precio", "comprar", "presupuesto", "hoy")
            human_request_keywords = @("asesor", "persona", "humano")
        }
    }
} | ConvertTo-Json -Depth 10

$configResponse = curl -s -X POST "http://localhost:8000/api/tenants/$TenantId/configs" `
    -H "Content-Type: application/json" `
    -H "X-API-Key: $ApiKey" `
    -d $configBody

Write-Host "✅ Configuration created" -ForegroundColor Green

# Test the tenant
Write-Host "`nStep 3: Testing tenant..." -ForegroundColor Yellow
$testBody = @{
    tenant_slug = $TenantSlug
    channel = "whatsapp"
    contact_phone = "595981000000"
    contact_name = "Test User"
    text_content = "Hola, ¿cuánto cuesta la madera de pino?"
} | ConvertTo-Json

$testResponse = curl -s -X POST http://localhost:8000/api/test/process-message `
    -H "Content-Type: application/json" `
    -H "X-API-Key: $ApiKey" `
    -d $testBody | ConvertFrom-Json

if ($testResponse.success) {
    Write-Host "✅ Test message processed successfully!" -ForegroundColor Green
    Write-Host "   Message ID: $($testResponse.message_id)" -ForegroundColor Cyan
    Write-Host "   Lead ID: $($testResponse.lead_id)" -ForegroundColor Cyan
    if ($testResponse.response_text) {
        Write-Host "   Response: $($testResponse.response_text.Substring(0, [Math]::Min(80, $testResponse.response_text.Length)))..." -ForegroundColor Cyan
    }
} else {
    Write-Host "⚠️  Test message failed:" -ForegroundColor Yellow
    Write-Host $testResponse -ForegroundColor Yellow
}

# Summary
Write-Host "`n==================================" -ForegroundColor Green
Write-Host "Tenant Setup Complete!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green
Write-Host ""
Write-Host "Tenant Details:" -ForegroundColor Cyan
Write-Host "  Slug: $TenantSlug" -ForegroundColor Cyan
Write-Host "  ID: $TenantId" -ForegroundColor Cyan
Write-Host "  Name: $BusinessName" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Integrate WhatsApp: Set webhook in Meta Dashboard" -ForegroundColor Yellow
Write-Host "2. Configure email: Update SMTP settings in .env" -ForegroundColor Yellow
Write-Host "3. View API docs: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
