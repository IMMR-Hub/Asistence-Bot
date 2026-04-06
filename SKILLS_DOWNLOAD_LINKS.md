# 6 Skills a Descargar/Instalar
## Universal Sales Automation Core

---

## 📥 INSTALACIÓN RÁPIDA

### Opción A: Desde el CLI de Claude Code
```bash
# En la terminal, ejecutar:
/fastapi-expert
/python-backend-expert
/postgres-expert
/debug-systematic
# Para Claude-Mem y Skill-Creator, ver instrucciones abajo
```

### Opción B: Descargar desde GitHub

---

## 1️⃣ FastAPI Expert Skill

**Link directo:** https://github.com/Jeffallan/claude-skills/tree/main/skills/backend/fastapi-expert

**Instalación:**
```bash
git clone https://github.com/Jeffallan/claude-skills.git
# Copiar carpeta fastapi-expert a .claude/skills/
```

**O desde marketplace:**
https://mcpmarket.com/tools/skills/fastapi-production-toolkit

---

## 2️⃣ Python Backend Expert Skill

**Link directo:** https://github.com/Jeffallan/claude-skills/tree/main/skills/backend/python-expert

**Instalación:** Incluido en mismo repo que FastAPI Expert

---

## 3️⃣ PostgreSQL Expert Skill

**Link directo:** https://github.com/Jeffallan/claude-skills/tree/main/skills/database/postgres-expert

**Instalación:** Incluido en mismo repo

**Alternativa:**
https://mcpmarket.com/tools/skills/postgres-pro

---

## 4️⃣ Systematic Debugging Skill

**Link directo:** https://github.com/awesome-skills/systematic-debugging

**Instalación:**
```bash
git clone https://github.com/awesome-skills/systematic-debugging.git
# Copiar a .claude/skills/
```

**O desde marketplace:**
https://mcpmarket.com/tools/skills/systematic-code-debugging

**Incluye también la skill 5-Whys:**
https://github.com/awesome-skills/5-whys-skill

---

## 5️⃣ Claude-Mem (Memory Management)

**Link directo:** https://github.com/thedotmack/claude-mem

**Instalación (Manual - más complejo):**
```bash
git clone https://github.com/thedotmack/claude-mem.git
# Seguir README.md para setup
```

**Documentación:** https://docs.claude-mem.ai/introduction

**Alternativa (Más simple): Persistent Memory Skills**
https://github.com/gyowork55/cowork-session-skills
```bash
git clone https://github.com/gyowork55/cowork-session-skills.git
# Incluye /standup y /conclude
```

---

## 6️⃣ Skill Creator (Meta-Skill)

**Link directo:** https://github.com/anthropic-skills/skill-creator

**Documentación oficial:** https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

**Instalación:**
```bash
# Ya debería estar disponible como comando nativo en Claude Code
/skill-creator
```

**Si necesitas instalación manual:**
https://marketplace.anthropic.com/skills/skill-creator

---

## 🚀 FLUJO DE INSTALACIÓN RECOMENDADO

### Paso 1: Descargar Repo Principal (Jeffallan)
```bash
git clone https://github.com/Jeffallan/claude-skills.git
cd claude-skills
# Contiene: FastAPI Expert, Python Backend Expert, PostgreSQL Expert
```

### Paso 2: Copiar a .claude/skills/
```bash
cp -r claude-skills/skills/backend/fastapi-expert ~/.claude/skills/
cp -r claude-skills/skills/backend/python-expert ~/.claude/skills/
cp -r claude-skills/skills/database/postgres-expert ~/.claude/skills/
```

### Paso 3: Descargar Debugging Skill
```bash
git clone https://github.com/awesome-skills/systematic-debugging.git
cp -r systematic-debugging ~/.claude/skills/
```

### Paso 4: Descargar Memory Skill (Opción Simple)
```bash
git clone https://github.com/gyowork55/cowork-session-skills.git
cp -r cowork-session-skills ~/.claude/skills/
```

### Paso 5: Skill Creator (Nativo)
Ya debería estar disponible como `/skill-creator`

---

## ✅ VERIFICACIÓN

Después de instalar, en Claude Code prueba:
```
/fastapi-expert → debe responder
/python-backend-expert → debe responder
/postgres-expert → debe responder
/debug-systematic → debe responder
/standup → debe responder (si instalaste memory skill)
/conclude → debe responder (si instalaste memory skill)
/skill-creator → debe responder
```

---

## 📝 NOTAS

- **Carpeta .claude/skills/**: Debe estar en raíz del proyecto
- **Permisos**: Los scripts deben ser ejecutables en tu sistema
- **Claude Code**: Detecta skills automáticamente en .claude/skills/
- **Activación**: Se invocan con `/nombre-skill` o se cargan automáticamente cuando relevante

---

## 🆘 Si Algo Falla

1. Verifica que estén en: `C:\Users\Daniel\universal-sales-automation-core\.claude\skills\`
2. Verifica permisos: `ls -la .claude/skills/`
3. Recarga Claude Code: `Ctrl+Shift+P` → "Reload Window"
4. Si aún no funciona, usa `/skill-creator` para crear versión local

