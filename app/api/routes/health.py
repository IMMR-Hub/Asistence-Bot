from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.llm_client import get_ollama_client
from app.core.config import settings
import redis.asyncio as aioredis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "universal-sales-automation-core"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict:
    checks: dict[str, str] = {}

    # DB
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc}"

    # Redis
    r = aioredis.from_url(settings.REDIS_URL, socket_timeout=2)
    try:
        await r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
    finally:
        await r.aclose()

    # Ollama
    try:
        client = get_ollama_client()
        ok = await client.health_check()
        checks["ollama"] = "ok" if ok else "unavailable"
    except Exception as exc:
        checks["ollama"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }
