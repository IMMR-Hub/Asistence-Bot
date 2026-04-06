# /migrate-llm-provider

Migra el LLM de Ollama local (lento, 40-60s) a Together.ai via API (rápido, <5s).

## Pre-requisitos
- API Key de Together.ai (obtener en https://api.together.xyz → Sign up gratis, $1 de crédito inicial)
- Guardar la key en un lugar seguro antes de continuar

## Ejecución completa

Seguir la skill `llm-provider-migrator` con estos parámetros para Together.ai:

```
LLM_PROVIDER=together
LLM_API_BASE=https://api.together.xyz/v1
LLM_CLASSIFY_MODEL=meta-llama/Llama-3.1-8B-Instruct-Turbo
LLM_RESPONSE_MODEL=meta-llama/Llama-3.1-70B-Instruct-Turbo
```

## Secuencia de cambios

1. Agregar variables al `docker-compose.yml`
2. Actualizar `app/core/config.py` con nuevas settings
3. Crear/actualizar cliente LLM genérico con factory pattern
4. Actualizar `classifier.py` para usar cliente genérico
5. Actualizar `orchestrator.py` para usar cliente genérico
6. Implementar routing inteligente (FAQ directa → sin LLM)
7. Recrear container: `docker compose up -d --no-deps api`
8. Medir latencia con test inbound
9. Correr 20 conversation tests
10. Verificar fallback a Ollama si Together falla

## Criterio de cierre

- [ ] Latencia de respuesta < 5 segundos en mensaje simple
- [ ] Latencia de respuesta < 10 segundos en mensaje complejo
- [ ] FAQs directas responden en < 1 segundo (sin invocar LLM)
- [ ] Si Together.ai no responde: sistema usa Ollama como fallback
- [ ] Todos los 20 conversation tests pasan
- [ ] `LLM_PROVIDER` es configurable por env var, no hardcodeado

## Modelos alternativos si Llama-3.1 no está disponible

| Modelo | Velocidad | Calidad | Costo |
|---|---|---|---|
| `meta-llama/Llama-3.1-8B-Instruct-Turbo` | Muy rápido | Buena clasificación | $0.18/1M tokens |
| `meta-llama/Llama-3.1-70B-Instruct-Turbo` | Rápido | Excelente respuestas | $0.88/1M tokens |
| `Qwen/Qwen2.5-7B-Instruct-Turbo` | Muy rápido | Buena (familiar al código) | $0.30/1M tokens |
| `mistralai/Mistral-7B-Instruct-v0.3` | Rápido | Buena | $0.20/1M tokens |
