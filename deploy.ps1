# ════════════════════════════════════════════════════════════════════════════
# PowerShell Deploy Script para Universal Sales Automation Core
# Uso: .\deploy.ps1 -environment dev  (o 'prod')
# ════════════════════════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "prod")]
    [string]$environment = "dev",

    [Parameter(Mandatory=$false)]
    [switch]$logs = $false,

    [Parameter(Mandatory=$false)]
    [switch]$rebuild = $false
)

$ErrorActionPreference = "Stop"

# Colores para output
$colors = @{
    Success = "Green"
    Warning = "Yellow"
    Error = "Red"
    Info = "Cyan"
}

function Write-Log {
    param([string]$message, [string]$type = "Info")
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] $message" -ForegroundColor $colors[$type]
}

# ════════════════════════════════════════════════════════════════════════════
# FUNCIÓN: Verificar docker
# ════════════════════════════════════════════════════════════════════════════
function Test-Docker {
    Write-Log "Verificando Docker..." -type "Info"
    try {
        $dockerVersion = docker --version
        Write-Log "✅ Docker encontrado: $dockerVersion" -type "Success"
        return $true
    } catch {
        Write-Log "❌ Docker no está instalado o no está en PATH" -type "Error"
        Write-Log "Descarga desde: https://www.docker.com/products/docker-desktop" -type "Warning"
        exit 1
    }
}

# ════════════════════════════════════════════════════════════════════════════
# FUNCIÓN: Levantar containers
# ════════════════════════════════════════════════════════════════════════════
function Start-Containers {
    param([string]$env)

    if ($env -eq "prod") {
        Write-Log "🚀 Levantando containers PRODUCCIÓN..." -type "Warning"
        if (!(Test-Path ".env.production")) {
            Write-Log "❌ CRÍTICO: .env.production NO existe" -type "Error"
            Write-Log "Por favor, crea .env.production con credenciales reales" -type "Warning"
            exit 1
        }
        docker-compose -f docker-compose.prod.yml up -d
    } else {
        Write-Log "🚀 Levantando containers DESARROLLO..." -type "Info"
        docker-compose up -d
    }

    Write-Log "⏳ Esperando que los services estén healthy..." -type "Info"
    Start-Sleep -Seconds 5
}

# ════════════════════════════════════════════════════════════════════════════
# FUNCIÓN: Reconstruir imágenes
# ════════════════════════════════════════════════════════════════════════════
function Rebuild-Images {
    param([string]$env)

    Write-Log "🔨 Reconstruyendo imágenes Docker..." -type "Warning"
    if ($env -eq "prod") {
        docker-compose -f docker-compose.prod.yml build --no-cache
    } else {
        docker-compose build --no-cache
    }
    Write-Log "✅ Imágenes reconstruidas" -type "Success"
}

# ════════════════════════════════════════════════════════════════════════════
# FUNCIÓN: Ver logs
# ════════════════════════════════════════════════════════════════════════════
function Show-Logs {
    param([string]$env)

    Write-Log "📋 Mostrando logs (Ctrl+C para salir)..." -type "Info"
    if ($env -eq "prod") {
        docker-compose -f docker-compose.prod.yml logs -f api
    } else {
        docker-compose logs -f api
    }
}

# ════════════════════════════════════════════════════════════════════════════
# FUNCIÓN: Health check
# ════════════════════════════════════════════════════════════════════════════
function Test-Health {
    param([string]$env)

    Write-Log "🏥 Verificando salud del sistema..." -type "Info"

    $port = if ($env -eq "prod") { "8000" } else { "8000" }
    $maxRetries = 30
    $retry = 0

    while ($retry -lt $maxRetries) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$port/health" -ErrorAction Stop
            Write-Log "✅ API saludable (HTTP $($response.StatusCode))" -type "Success"
            return $true
        } catch {
            $retry++
            Write-Log "⏳ API iniciando... intento $retry/$maxRetries" -type "Warning"
            Start-Sleep -Seconds 2
        }
    }

    Write-Log "❌ API no respondió después de $maxRetries intentos" -type "Error"
    return $false
}

# ════════════════════════════════════════════════════════════════════════════
# FUNCIÓN: Status
# ════════════════════════════════════════════════════════════════════════════
function Show-Status {
    param([string]$env)

    Write-Log "📊 Estado de containers:" -type "Info"
    if ($env -eq "prod") {
        docker-compose -f docker-compose.prod.yml ps
    } else {
        docker-compose ps
    }
}

# ════════════════════════════════════════════════════════════════════════════
# FUNCIÓN: Stop
# ════════════════════════════════════════════════════════════════════════════
function Stop-Containers {
    param([string]$env)

    Write-Log "⛔ Deteniendo containers..." -type "Warning"
    if ($env -eq "prod") {
        docker-compose -f docker-compose.prod.yml down
    } else {
        docker-compose down
    }
    Write-Log "✅ Containers detenidos" -type "Success"
}

# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

Write-Log "========================================" -type "Info"
Write-Log "Universal Sales Automation Deploy Tool" -type "Info"
Write-Log "Ambiente: $environment" -type "Warning"
Write-Log "========================================" -type "Info"

# Test Docker
Test-Docker

# Validar que estamos en el directorio correcto
if (!(Test-Path "docker-compose.yml")) {
    Write-Log "❌ Error: No estoy en el directorio raíz del proyecto" -type "Error"
    exit 1
}

# Ejecutar acciones
if ($rebuild) {
    Rebuild-Images $environment
}

Start-Containers $environment
Start-Sleep -Seconds 3

Test-Health $environment
Show-Status $environment

if ($logs) {
    Show-Logs $environment
}

Write-Log "✅ Deploy completado!" -type "Success"
Write-Log "API disponible en: http://localhost:8000" -type "Info"
Write-Log "Docs en: http://localhost:8000/docs" -type "Info"

# ════════════════════════════════════════════════════════════════════════════
# OTROS COMANDOS ÚTILES
# ════════════════════════════════════════════════════════════════════════════
Write-Log "" -type "Info"
Write-Log "📝 Otros comandos útiles:" -type "Info"
Write-Log "  .\deploy.ps1 -environment prod          # Deploy a producción" -type "Info"
Write-Log "  .\deploy.ps1 -logs                     # Ver logs en vivo" -type "Info"
Write-Log "  .\deploy.ps1 -rebuild                  # Reconstruir imágenes" -type "Info"
Write-Log "" -type "Info"
