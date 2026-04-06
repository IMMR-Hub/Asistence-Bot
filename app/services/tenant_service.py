from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tenant import Tenant
from app.db.repositories.tenant_repo import TenantRepository
from app.schemas.tenant import TenantConfigSchema, TenantCreate
from app.core.logging import get_logger

logger = get_logger(__name__)


class TenantService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = TenantRepository(session)

    async def create_tenant(self, data: TenantCreate) -> Tenant:
        existing = await self.repo.get_by_slug(data.tenant_slug)
        if existing:
            raise ValueError(f"Tenant '{data.tenant_slug}' already exists")

        tenant = Tenant(
            tenant_slug=data.tenant_slug,
            business_name=data.business_name,
            timezone=data.timezone,
            default_language=data.default_language,
            industry_tag=data.industry_tag,
        )
        return await self.repo.save(tenant)

    async def get_tenant(self, tenant_id: uuid.UUID) -> Tenant | None:
        return await self.repo.get_by_id(tenant_id)

    async def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        return await self.repo.get_by_slug(slug)

    async def upsert_config(
        self, tenant_id: uuid.UUID, config_data: TenantConfigSchema
    ) -> None:
        # Get current version BEFORE deactivating
        prev = await self.repo.get_active_config(tenant_id)
        next_version = (prev.version + 1) if prev else 1

        # Deactivate all previous active configs
        await self.repo.deactivate_previous_configs(tenant_id)

        await self.repo.create_config(
            tenant_id=tenant_id,
            config_data=config_data.model_dump(),
            version=next_version,
        )
        logger.info("tenant_config_upserted", tenant_id=str(tenant_id), version=next_version)

    async def load_active_config(self, tenant_id: uuid.UUID) -> TenantConfigSchema | None:
        cfg = await self.repo.get_active_config(tenant_id)
        if not cfg:
            return None
        return TenantConfigSchema.model_validate(cfg.config_json)
