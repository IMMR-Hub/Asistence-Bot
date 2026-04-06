# /fix-worker

Diagnostica y corrige el RQ Worker que está en estado UNHEALTHY. El worker es el motor de follow-ups — si falla, los seguimientos automáticos no se ejecutan.

## Diagnóstico (ejecutar en orden)

### Paso 1: Estado actual
```bash
docker ps --filter name=salesbot_worker
docker logs salesbot_worker --tail=50
```

### Paso 2: Identificar causa raíz
Buscar en los logs:
- Error de conexión a Redis → problema de red o URL
- ImportError → import de job o módulo roto
- ModuleNotFoundError → dependencia faltante
- Connection refused → Redis no está listo cuando worker arranca
- Healthcheck fails → el comando de healthcheck está mal configurado

### Paso 3: Verificar Redis
```bash
docker compose exec redis redis-cli ping
# Esperado: PONG
```

### Paso 4: Verificar que el worker puede importar los jobs
```bash
docker compose exec worker python -c "from app.workers.jobs import send_follow_up; print('OK')"
```

## Correcciones según causa raíz

### Si es problema de healthcheck mal configurado
En `docker-compose.yml`, el worker debe tener:
```yaml
worker:
  healthcheck:
    test: ["CMD", "python", "-c", "import redis; r = redis.from_url('${REDIS_URL}'); r.ping(); from rq import Queue; q = Queue(connection=r); print('healthy')"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

### Si es problema de imports rotos
Verificar `app/workers/worker.py` y `app/workers/jobs.py`.
Correr lint: `docker compose exec worker python -m py_compile app/workers/worker.py`

### Si es problema de dependencias
```bash
docker compose exec worker pip list | grep rq
docker compose exec worker pip list | grep redis
```

### Si es problema de timing (Redis no listo)
Agregar `depends_on` con condición en docker-compose.yml:
```yaml
worker:
  depends_on:
    redis:
      condition: service_healthy
    db:
      condition: service_healthy
```

## Verificación post-corrección

```bash
# 1. Recrear worker
docker compose up -d --no-deps worker

# 2. Esperar 30 segundos y verificar estado
docker ps --filter name=salesbot_worker

# 3. Encolar un job de prueba
docker compose exec api python -c "
from rq import Queue
import redis
r = redis.from_url('redis://redis:6379/0')
q = Queue('default', connection=r)
print(f'Jobs en cola: {len(q)}')
print(f'Workers activos: {q.count}')
"

# 4. Verificar que el worker procesa
docker logs salesbot_worker --tail=20
```

## Criterio de cierre

- [ ] `docker ps` muestra `salesbot_worker` como `Up (healthy)`
- [ ] No hay errores en logs del worker
- [ ] Worker puede conectarse a Redis
- [ ] Worker puede importar jobs
- [ ] Un follow-up de prueba se encola y se ejecuta correctamente

Usar skill `bugfix-executor` para cada cambio de código y `strict-code-review` antes de cerrar.
