# setup.ps1 - Automated setup script for Windows PowerShell

Write-Host "==================================" -ForegroundColor Green
Write-Host "Universal Sales Automation Setup" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green
Write-Host ""

# Check if Docker is installed
Write-Host "Checking Docker installation..." -ForegroundColor Yellow
$dockerCheck = docker --version 2>$null
if ($dockerCheck) {
    Write-Host "✅ Docker found: $dockerCheck" -ForegroundColor Green
} else {
    Write-Host "❌ Docker not found. Please install from https://www.docker.com/products/docker-desktop" -ForegroundColor Red
    exit 1
}

# Copy .env if needed
if (!(Test-Path ".env")) {
    Write-Host "`nCopying .env.example to .env..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "✅ .env created (edit with your values if needed)" -ForegroundColor Green
} else {
    Write-Host "✅ .env already exists" -ForegroundColor Green
}

# Start Docker Compose
Write-Host "`nStarting services with Docker Compose..." -ForegroundColor Yellow
docker compose up --build -d

# Wait for services to be ready
Write-Host "`nWaiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check health
Write-Host "`nVerifying services..." -ForegroundColor Yellow
$maxRetries = 10
$retryCount = 0

while ($retryCount -lt $maxRetries) {
    try {
        $healthCheck = curl -s http://localhost:8000/health | ConvertFrom-Json
        if ($healthCheck.status -eq "ok") {
            Write-Host "✅ API is running" -ForegroundColor Green
            break
        }
    } catch {
        $retryCount++
        Write-Host "Attempt $retryCount/$maxRetries - Waiting for API..." -ForegroundColor Gray
        Start-Sleep -Seconds 3
    }
}

# Final status
Write-Host "`n==================================" -ForegroundColor Green
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green
Write-Host ""
Write-Host "📍 API:     http://localhost:8000" -ForegroundColor Cyan
Write-Host "📚 Docs:    http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "🗄️  Database: postgres://localhost:5432" -ForegroundColor Cyan
Write-Host "⚡ Redis:    redis://localhost:6379" -ForegroundColor Cyan
Write-Host "🤖 Ollama:   http://localhost:11434" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env with your API key and WhatsApp credentials" -ForegroundColor Yellow
Write-Host "2. Run: .\create-tenant.ps1 to create your first tenant" -ForegroundColor Yellow
Write-Host "3. Check logs: docker compose logs api" -ForegroundColor Yellow
Write-Host ""
