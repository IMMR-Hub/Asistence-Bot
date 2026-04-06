# Claude Code Skills Setup
## Universal Sales Automation Core

Este archivo documenta las 5 skills críticas instaladas para este proyecto.

### 1. FastAPI Expert Skill
**Propósito:** Validar y mejorar código FastAPI, async/await patterns, SQLAlchemy async
**Repositorio:** https://github.com/Jeffallan/claude-skills
**Invocación:** `/fastapi-expert`
**Cuándo usarla:** Cambios en app/, routes/, services/, database code
**Previene:** Errores con env vars, lru_cache, async sessions, context management

### 2. Python Backend Expert Skill
**Propósito:** Best practices Python backend, patterns, error handling
**Repositorio:** https://github.com/Jeffallan/claude-skills
**Invocación:** `/python-backend-expert`
**Cuándo usarla:** Cambios en lógica de negocio, módulos, servicios
**Previene:** Errores de diseño, performance issues, code quality

### 3. PostgreSQL Expert Skill
**Propósito:** Optimización de queries, schema design, migrations
**Repositorio:** https://github.com/Jeffallan/claude-skills
**Invocación:** `/postgres-expert`
**Cuándo usarla:** Cambios en models/, migrations/, queries
**Previene:** N+1 queries, migration issues, data consistency problems

### 4. Systematic Debugging Skill (Root Cause First)
**Propósito:** Análisis sistemático de errores con CLAUDE method (Collect, List, Analyze, Understand, Determine)
**Repositorio:** https://mcpmarket.com/tools/skills/systematic-code-debugging
**Invocación:** `/debug-systematic` o `/5-whys`
**Cuándo usarla:** Cuando hay bugs o errores sin entender origen
**Previene:** Intentar fixes sin root cause, perder tiempo en síntomas

### 5. Claude-Mem (Persistent Memory + Context Management)
**Propósito:** Mantener contexto entre sesiones, comprimir observaciones, evitar olvidos
**Repositorio:** https://github.com/thedotmack/claude-mem
**Invocación:** Automático + `/standup` y `/conclude` en cada sesión
**Cuándo usarla:** Inicio y cierre de cada sesión de trabajo
**Previene:** Context loss, repetir errores, perder detalles del proyecto

---

### 6. Skill Creator (Meta-Skill)
**Propósito:** Crear nuevas skills según necesidad del proyecto
**Repositorio:** https://github.com/anthropic-skills/skill-creator
**Invocación:** `/skill-creator`
**Cuándo usarla:** Cuando necesites una skill específica que no exista
**Ejemplos de skills a crear:**
- Multi-Tenant Config Validator
- Webhook Tester
- Tenant Onboarding Guide
- LLM Model Selector

---

## Flujo de Uso Recomendado

### Inicio de Sesión
```
/standup
→ Resumen de sesiones anteriores, estado actual, qué quedó pendiente
```

### Durante el Desarrollo
```
1. Cambio código FastAPI/routes
   → /fastapi-expert

2. Cambio lógica de negocio
   → /python-backend-expert

3. Cambio models/queries
   → /postgres-expert

4. Bug sin solución
   → /debug-systematic (root cause first)

5. Code review general
   → /simplify (built-in)

6. Necesitas skill nueva
   → /skill-creator (crea skill personalizada)
```

### Cierre de Sesión
```
/conclude
→ Registra avances, nuevos aprendizajes, siguientes pasos
→ Claude-Mem comprime y persiste para próxima sesión
```

---

## Cambios al Proyecto

Estas skills se activarán automáticamente cuando:
- Edites archivos en `app/` (FastAPI Expert)
- Cambies `app/db/models/` (PostgreSQL Expert)
- Modifiques servicios/lógica (Python Backend Expert)
- Encuentres errores (Systematic Debugging)

No requieren configuración adicional. Solo usa los comandos cuando necesites.

---

## Ventaja Inmediata

✅ Menos errores Docker (FastAPI Expert)
✅ Menos env var issues (FastAPI Expert)
✅ Root cause analysis automático (Systematic Debugging)
✅ Contexto persiste entre sesiones (Claude-Mem)
✅ Code quality mejora (Python Backend Expert)
