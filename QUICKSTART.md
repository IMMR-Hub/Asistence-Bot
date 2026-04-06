# ⚡ Quick Start Guide

## 3 Pasos para Empezar

### Paso 1: Iniciar (1 minuto)
```powershell
# Abre PowerShell en la carpeta del proyecto y ejecuta:
.\setup.ps1
```

### Paso 2: Crear Tenant (2 minutos)
```powershell
# Crea tu primer tenant:
.\create-tenant.ps1
```

### Paso 3: Probar (1 minuto)
```powershell
# En PowerShell, prueba una consulta:
$API_KEY = "tu-api-secret-key"

curl -X POST http://localhost:8000/api/test/process-message `
  -H "Content-Type: application/json" `
  -H "X-API-Key: $API_KEY" `
  -d '{"tenant_slug":"forestal-caaguazu","channel":"whatsapp","contact_phone":"595981000000","text_content":"Hola"}' `
  | ConvertFrom-Json | ConvertTo-Json
```

## URLs Útiles

- **API Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health
- **Status**: http://localhost:8000/ready

## Comandos Útiles

```powershell
# Ver estado
.\manage.ps1 status

# Ver logs en tiempo real
.\manage.ps1 logs

# Reiniciar servicios
.\manage.ps1 restart

# Correr tests
.\manage.ps1 test

# Limpiar todo
.\manage.ps1 clean
```

## Estructura de Archivos

```
universal-sales-automation-core/
├── app/                          # Código Python
├── alembic/                      # Migraciones BD
├── docker-compose.yml           # Servicios Docker
├── Dockerfile                   # API container
├── requirements.txt             # Python packages
├── .env.example                 # Ejemplo de config
├── README.md                    # Documentación
├── QUICKSTART.md               # Este archivo
├── setup.ps1                   # Script de instalación
├── create-tenant.ps1           # Script crear tenant
└── manage.ps1                  # Script de gestión
```

## Solucionar Problemas

### "API no responde"
```powershell
.\manage.ps1 logs
```

### "Database error"
```powershell
# Limpia y reinicia todo
.\manage.ps1 clean
.\setup.ps1
```

### "Puerto en uso"
Cambia los puertos en docker-compose.yml:
- API: 8000 → 8001
- PostgreSQL: 5432 → 5433
- etc.

## ¿Qué Viene Next?

1. ✅ Setup completado
2. ✅ Tenant creado
3. 🔄 Conectar WhatsApp real
4. 📧 Configurar email
5. 🚀 Desplegar a producción

## Documentación Completa

Ver `README.md` para documentación detallada.
