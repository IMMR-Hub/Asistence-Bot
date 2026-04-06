@echo off
chcp 65001 >/dev/null
cls
echo.
echo ================================
echo Universal Sales Automation
echo ================================
echo.
echo Verificando Docker...
docker --version >/dev/null 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker no está instalado
    echo Descárgalo en: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo ✅ Docker encontrado
echo.
echo Iniciando servicios (esto toma 1-2 minutos)...
echo.
cd /d C:\Users\Daniel\universal-sales-automation-core
docker compose up --build -d
echo.
echo Esperando a que los servicios se inicien...
timeout /t 5 /nobreak
echo.
echo Verificando servicios...
:retry
for /f "tokens=*" %%i in ('curl -s http://localhost:8000/health 2^>nul') do set response=%%i
if "%response%"=="" (
    echo Aún cargando... por favor espere
    timeout /t 3 /nobreak
    goto retry
)
echo.
echo ================================
echo ✅ ¡TODO LISTO!
echo ================================
echo.
echo 🌐 Acceso a tu aplicación:
echo    http://localhost:8000
echo.
echo 📚 Documentación interactiva:
echo    http://localhost:8000/docs
echo.
echo 🔍 Ver estado:
echo    http://localhost:8000/ready
echo.
echo Presiona ENTER para salir
pause
