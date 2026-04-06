from __future__ import annotations

import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import *  # noqa: F401,F403

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_sales_automation"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_tenant_config_dict() -> dict:
    return {
        "tenant_slug": "test-tenant",
        "business_name": "Test Business",
        "timezone": "UTC",
        "default_language": "es",
        "enabled_channels": ["whatsapp", "email"],
        "enabled_modules": [
            "inbound_router", "intent_classifier", "entity_extractor",
            "response_orchestrator", "knowledge_resolver", "crm_writer",
            "follow_up_engine", "human_escalation", "audit_logger",
            "whatsapp_adapter", "email_adapter",
        ],
        "brand_tone": "professional",
        "business_hours": {
            "monday_to_friday": "08:00-18:00",
            "saturday": "closed",
            "sunday": "closed",
        },
        "faq_entries": [
            {"question": "horario", "answer": "Lunes a viernes 8-18."},
        ],
        "escalation_rules": {
            "confidence_threshold": 0.72,
            "always_escalate_hot_leads": False,
            "always_escalate_complaints": True,
        },
        "follow_up_rules": [
            {
                "rule_key": "warm_lead_no_reply",
                "delay_minutes": 120,
                "channel": "same_as_origin",
                "enabled": True,
            }
        ],
        "classification_overrides": {
            "hot_keywords": ["comprar", "precio"],
            "human_request_keywords": ["humano", "asesor"],
        },
    }
