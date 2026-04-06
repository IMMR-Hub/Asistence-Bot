# /deploy-staging

Ejecuta un deploy completo y verificado al ambiente de staging local.

## Qué hace este comando

Ejecuta la skill `staging-deployer` completa:
1. Build sin caché
2. Up de todos los servicios
3. Migraciones
4. Health check
5. Ready check
6. Test inbound sintético
7. Verificación de worker

## Antes de ejecutar

Verificar:
- [ ] Docker Desktop está corriendo
- [ ] No hay cambios sin commitear que puedan romper el deploy
- [ ] `.env` tiene todas las variables actualizadas
- [ ] La API key de LLM provider está configurada

## Resultado esperado

```
=== STAGING DEPLOY: OK ===
Build: PASS
Containers: PASS
Migrations: PASS
/health: PASS
/ready: PASS
Inbound test: PASS — respuesta generada en <5s
Worker: HEALTHY
```

Si algún paso falla: NO continuar. Ver logs y usar `/fix-worker` o `bugfix-executor` según corresponda.

## Guardar log

El resultado se guarda en `DEPLOY_LOG.md` con fecha y commit hash.
