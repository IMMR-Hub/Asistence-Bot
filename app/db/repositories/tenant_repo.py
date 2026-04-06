from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tenant import Tenant, TenantConfig
from app.db.repositories.base_repo import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Tenant)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self.session.execute(
            select(Tenant).where(Tenant.tenant_slug == slug, Tenant.status_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_active_config(self, tenant_id: uuid.UUID) -> TenantConfig | None:
        result = await self.session.execute(
            select(TenantConfig)
            .where(
                TenantConfig.tenant_id == tenant_id,
                TenantConfig.is_active.is_(True),
            )
            .order_by(TenantConfig.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def deactivate_previous_configs(self, tenant_id: uuid.UUID) -> None:
        await self.session.execute(
            update(TenantConfig)
            .where(TenantConfig.tenant_id == tenant_id)
            .values(is_active=False)
        )
        await self.session.flush()

    async def create_config(self, tenant_id: uuid.UUID, config_data: dict, version: int) -> TenantConfig:
        config = TenantConfig(
            tenant_id=tenant_id,
            config_json=config_data,
            version=version,
            is_active=True,
        )
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)
        return config


class TenantConfigRepository(BaseRepository[TenantConfig]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantConfig)
