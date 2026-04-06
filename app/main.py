from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging("DEBUG" if settings.DEBUG else "INFO")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "startup",
        env=settings.APP_ENV,
        port=settings.APP_PORT,
        ollama=settings.OLLAMA_BASE_URL,
    )
    # Warm-up: verify DB connectivity (will surface misconfiguration early)
    from app.db.session import engine
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("db_connected")
    except Exception as exc:
        logger.error("db_connection_failed", error=str(exc))

    yield

    logger.info("shutdown")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Universal Sales Automation Core",
        version="1.0.0",
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.routes.health import router as health_router
    from app.api.routes.tenants import router as tenants_router
    from app.api.routes.webhooks import router as webhooks_router

    app.include_router(health_router)
    app.include_router(tenants_router)
    app.include_router(webhooks_router)

    return app


app = create_app()
