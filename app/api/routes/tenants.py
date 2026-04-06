from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import api_key_required
from app.db.session import get_db
from app.schemas.lead import EscalationRead, LeadRead
from app.schemas.tenant import TenantConfigCreate, TenantConfigRead, TenantCreate, TenantRead
from app.services.tenant_service import TenantService
from app.db.repositories.lead_repo import LeadRepository
from app.db.repositories.conversation_repo import ConversationRepository
from app.db.repositories.escalation_repo import EscalationRepository

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TenantRead)
async def create_tenant(
    data: TenantCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(api_key_required),
) -> TenantRead:
    svc = TenantService(db)
    try:
        tenant = await svc.create_tenant(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return TenantRead.model_validate(tenant)


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(api_key_required),
) -> TenantRead:
    svc = TenantService(db)
    tenant = await svc.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return TenantRead.model_validate(tenant)


@router.post("/{tenant_id}/configs", status_code=status.HTTP_201_CREATED)
async def upsert_tenant_config(
    tenant_id: uuid.UUID,
    data: TenantConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(api_key_required),
) -> dict:
    svc = TenantService(db)
    tenant = await svc.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    await svc.upsert_config(tenant_id, data.config)
    return {"status": "ok", "tenant_id": str(tenant_id)}


@router.get("/{tenant_id}/leads", response_model=list[LeadRead])
async def list_leads(
    tenant_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(api_key_required),
) -> list[LeadRead]:
    repo = LeadRepository(db)
    leads = await repo.list_by_tenant(tenant_id, limit=limit, offset=offset)
    return [LeadRead.model_validate(l) for l in leads]


@router.get("/{tenant_id}/conversations")
async def list_conversations(
    tenant_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(api_key_required),
) -> list[dict]:
    repo = ConversationRepository(db)
    convs = await repo.list_by_tenant(tenant_id, limit=limit, offset=offset)
    return [
        {
            "id": str(c.id),
            "contact_id": str(c.contact_id),
            "channel": c.channel,
            "status": c.status,
            "escalated": c.escalated,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
            "created_at": c.created_at.isoformat(),
        }
        for c in convs
    ]


@router.get("/{tenant_id}/escalations", response_model=list[EscalationRead])
async def list_escalations(
    tenant_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(api_key_required),
) -> list[EscalationRead]:
    repo = EscalationRepository(db)
    escs = await repo.list_by_tenant(tenant_id, limit=limit, offset=offset)
    return [EscalationRead.model_validate(e) for e in escs]
