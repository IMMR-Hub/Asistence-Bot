from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.contact import Contact
from app.db.repositories.base_repo import BaseRepository


class ContactRepository(BaseRepository[Contact]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Contact)

    async def get_by_external_id(self, tenant_id: uuid.UUID, external_id: str) -> Contact | None:
        result = await self.session.execute(
            select(Contact).where(
                Contact.tenant_id == tenant_id,
                Contact.external_contact_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, tenant_id: uuid.UUID, phone: str) -> Contact | None:
        result = await self.session.execute(
            select(Contact).where(
                Contact.tenant_id == tenant_id,
                Contact.phone == phone,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, tenant_id: uuid.UUID, email: str) -> Contact | None:
        result = await self.session.execute(
            select(Contact).where(
                Contact.tenant_id == tenant_id,
                Contact.email == email,
            )
        )
        return result.scalar_one_or_none()
