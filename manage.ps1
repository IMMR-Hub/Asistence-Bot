# manage.ps1 - Docker Compose management script

param(
    [ValidateSet("start", "stop", "restart", "logs", "status", "clean", "test")]
    [string]$Action = "status"
)

switch ($Action) {
    "start" {
        Write-Host "Starting services..." -ForegroundColor Cyan
        docker compose up -d
        Start-Sleep -Seconds 3
        docker compose ps
    }
    
    "stop" {
        Write-Host "Stopping services..." -ForegroundColor Cyan
        docker compose down
    }
    
    "restart" {
        Write-Host "Restarting services..." -ForegroundColor Cyan
        docker compose restart
        Start-Sleep -Seconds 3
        docker compose ps
    }
    
    "logs" {
        Write-Host "Showing last 50 lines of logs (press Ctrl+C to exit)..." -ForegroundColor Cyan
        docker compose logs -f --tail=50
    }
    
    "status" {
        Write-Host "Service Status:" -ForegroundColor Cyan
        docker compose ps
        
        Write-Host "`nHealth Check:" -ForegroundColor Cyan
        try {
            $health = curl -s http://localhost:8000/health | ConvertFrom-Json
            Write-Host "API: $($health.status)" -ForegroundColor Green
        } catch {
            Write-Host "API: ❌ Not responding" -ForegroundColor Red
        }
        
        try {
            $ready = curl -s http://localhost:8000/ready | ConvertFrom-Json
            Write-Host "Database: $($ready.checks.db)" -ForegroundColor Green
            Write-Host "Redis: $($ready.checks.redis)" -ForegroundColor Green
            Write-Host "Ollama: $($ready.checks.ollama)" -ForegroundColor Green
        } catch {
            Write-Host "Dependencies: ❌ Check failed" -ForegroundColor Red
        }
    }
    
    "clean" {
        Write-Host "Cleaning up (removing containers and volumes)..." -ForegroundColor Yellow
        docker compose down -v
        Write-Host "✅ Cleaned" -ForegroundColor Green
    }
    
    "test" {
        Write-Host "Running tests..." -ForegroundColor Cyan
        docker compose exec api pytest app/tests/ -v
    }
    
    default {
        Write-Host "Usage: .\manage.ps1 [start|stop|restart|logs|status|clean|test]" -ForegroundColor Yellow
    }
}
