# SKILL: llm-provider-migrator

## Propósito
Migrar el sistema de Ollama (local, lento) a un proveedor LLM externo vía API (Together.ai, OpenAI-compatible). Objetivo: reducir latencia de 40-60s a menos de 5s.

## Proveedor recomendado: Together.ai
- Compatible con API OpenAI
- Modelo recomendado: `meta-llama/Llama-3.1-8B-Instruct-Turbo` (clasificación) y `meta-llama/Llama-3.1-70B-Instruct-Turbo` (respuestas)
- Precio: ~$0.18-$0.90 por 1M tokens
- Latencia: 1-4 segundos

## Variables de entorno a agregar en docker-compose.yml

```yaml
LLM_PROVIDER: "together"           # ollama | together | openai
LLM_API_KEY: "<your-together-api-key>"
LLM_API_BASE: "https://api.together.xyz/v1"
LLM_CLASSIFY_MODEL: "meta-llama/Llama-3.1-8B-Instruct-Turbo"
LLM_RESPONSE_MODEL: "meta-llama/Llama-3.1-70B-Instruct-Turbo"
LLM_TIMEOUT: "30"
LLM_FALLBACK_MODEL: "meta-llama/Llama-3.1-8B-Instruct-Turbo"
```

## Archivos a modificar

### 1. `app/core/config.py`
Agregar settings:
```python
LLM_PROVIDER: str = "ollama"  # ollama | together | openai
LLM_API_KEY: str = ""
LLM_API_BASE: str = "http://ollama:11434"
LLM_CLASSIFY_MODEL: str = "qwen2.5:7b-instruct"
LLM_RESPONSE_MODEL: str = "qwen2.5:14b-instruct"
LLM_TIMEOUT: int = 60
LLM_FALLBACK_MODEL: str = "qwen2.5:7b-instruct"
```

### 2. `app/services/llm_service.py` (o donde viva el cliente LLM)
Implementar factory pattern:
```python
def get_llm_client(settings) -> BaseLLMClient:
    if settings.LLM_PROVIDER == "ollama":
        return OllamaClient(base_url=settings.LLM_API_BASE, timeout=settings.LLM_TIMEOUT)
    elif settings.LLM_PROVIDER in ("together", "openai"):
        return OpenAICompatibleClient(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            timeout=settings.LLM_TIMEOUT
        )
    raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")
```

### 3. `app/modules/intent_classifier/classifier.py`
Reemplazar llamada directa a Ollama por llamada al cliente genérico.
Asegurarse que usa `LLM_CLASSIFY_MODEL`, no modelo hardcodeado.

### 4. `app/modules/response_orchestrator/orchestrator.py`
Reemplazar llamada directa a Ollama por llamada al cliente genérico.
Asegurarse que usa `LLM_RESPONSE_MODEL`, no modelo hardcodeado.

## Routing inteligente de inferencia (reducción de costo)

No todo mensaje necesita el modelo grande:
- FAQ directa (match exacto en knowledge_resolver) → no invocar LLM para respuesta, responder directo
- Clasificación → modelo pequeño siempre
- Respuesta con contexto complejo → modelo grande
- Escalación inmediata (hot_keywords match) → puede escalarse sin LLM

Implementar en `message_processor.py`:
```python
# Si knowledge_resolver encontró match exacto en FAQ, usar respuesta directa
if knowledge_result.exact_faq_match:
    return knowledge_result.faq_answer  # sin invocar LLM

# Para clasificación: siempre modelo pequeño
classification = await classifier.classify(message, model=settings.LLM_CLASSIFY_MODEL)

# Para respuesta: modelo según complejidad
model = settings.LLM_RESPONSE_MODEL if needs_complex_response else settings.LLM_FALLBACK_MODEL
```

## Secuencia de migración

1. Obtener API key de Together.ai (https://api.together.xyz)
2. Agregar variables al docker-compose.yml
3. Modificar config.py
4. Implementar factory de cliente LLM
5. Actualizar classifier y orchestrator
6. Correr test: `POST /api/test/process-message` con mensaje simple
7. Medir latencia: debe ser <5s
8. Correr los 20 conversation tests
9. Verificar que fallback funciona (simular error de Together.ai)

## Test de validación post-migración

```bash
# Medir latencia real
time curl -s -X POST http://localhost:8000/api/test/process-message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: salesbot-dev-key-2024" \
  -d '{"tenant_slug": "vitaclinica", "channel": "whatsapp", "sender_phone": "+595981000001", "message_text": "cuanto cuesta el blanqueamiento?"}'
```

Criterio de éxito: tiempo total < 5 segundos.

## Rollback
Si Together.ai falla: cambiar `LLM_PROVIDER: "ollama"` en docker-compose.yml y recrear container api.
Siempre tener Ollama como fallback de último recurso.
