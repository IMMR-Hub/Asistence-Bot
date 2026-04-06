# SKILL: ops-runbook-writer

## Propósito
Documentar procedimientos operativos críticos: deploy, rollback, incidentes, backups, restore. Genera documentación que cualquier miembro del equipo puede seguir sin conocer el código.

## Runbooks a generar

### Runbook 1: Deploy a staging
Documenta la secuencia completa del skill `staging-deployer` como documento ejecutable.

### Runbook 2: Deploy a producción
Igual que staging pero con:
- Verificación de backup previo
- Ventana de mantenimiento
- Notificación a clientes activos
- Monitoreo post-deploy por 30 minutos

### Runbook 3: Rollback
```
Trigger: deploy falla o comportamiento anómalo post-deploy

Pasos:
1. Identificar versión anterior estable (git log --oneline -5)
2. docker compose down
3. git checkout <versión-anterior>
4. docker compose up -d --build
5. Verificar /health y /ready
6. Correr test inbound sintético
7. Documentar incidente en INCIDENT_LOG.md
```

### Runbook 4: Incidente de producción
```
Trigger: /health falla, respuestas incorrectas, worker caído, canal no funciona

Clasificación:
P1 - Crítico: sistema no procesa ningún mensaje
P2 - Alto: canal específico caído o respuestas incorrectas en >20% casos
P3 - Medio: latencia alta pero sistema funcional
P4 - Bajo: UI/reporting, no afecta flujo de mensajes

Pasos P1:
1. docker ps → ver qué contenedor falla
2. docker logs <container> --tail=50 → identificar error
3. Si es DB: verificar conexión desde api
4. Si es Redis: verificar conexión desde worker
5. Si es LLM provider: verificar API key y límites
6. Aplicar fix mínimo o rollback
7. Verificar recuperación
8. Documentar en INCIDENT_LOG.md
```

### Runbook 5: Backup y restore de DB
```
Backup manual:
docker compose exec db pg_dump -U salesbot salesbot_db > backup_$(date +%Y%m%d_%H%M%S).sql

Restore:
docker compose exec -T db psql -U salesbot salesbot_db < backup_YYYYMMDD_HHMMSS.sql

Verificar restore:
docker compose exec api python -c "from app.db.session import engine; print('DB OK')"
```

### Runbook 6: Agregar nuevo tenant
```
1. Copiar template: tenants/template-setup.ps1 → tenants/<cliente>-setup.ps1
2. Editar datos del cliente en el script
3. Ejecutar: .\tenants\<cliente>-setup.ps1
4. Verificar en DB: GET /api/tenants/<slug>
5. Validar config: usar skill tenant-config-validator
6. Ejecutar test inbound sintético con el nuevo tenant
7. Activar en producción si todo PASS
```

### Runbook 7: Cambio de LLM provider
```
1. Actualizar docker-compose.yml:
   LLM_PROVIDER: "together"
   LLM_API_KEY: "<nueva-key>"
2. docker compose up -d --no-deps api
3. Verificar /health
4. Correr test inbound: medir latencia
5. Si latencia OK (<5s): DONE
6. Si falla: rollback a "ollama"
```

## Formato de runbook generado

Cada runbook debe tener:
- **Nombre**: [nombre del procedimiento]
- **Trigger**: cuándo ejecutar
- **Tiempo estimado**: X minutos
- **Prerrequisitos**: qué tener listo
- **Pasos numerados**: con comandos exactos
- **Criterio de éxito**: cómo saber que funcionó
- **Qué hacer si falla**: siguiente paso si un paso falla
- **Quién lo ejecuta**: rol responsable

## Archivo de salida
Guardar todos los runbooks en: `OPERATIONS_RUNBOOK.md`
Actualizar cuando cambien procedimientos.
