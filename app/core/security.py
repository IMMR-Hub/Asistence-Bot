from __future__ import annotations

import hashlib
import hmac

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def verify_meta_signature(payload: bytes, x_hub_signature_256: str) -> bool:
    """Verify Meta WhatsApp webhook signature."""
    if not settings.WEBHOOK_SIGNATURE_VERIFY:
        return True
    expected = (
        "sha256="
        + hmac.new(
            key=settings.WHATSAPP_ACCESS_TOKEN.encode(),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, x_hub_signature_256)


async def get_raw_body(request: Request) -> bytes:
    return await request.body()


def api_key_required(x_api_key: str = Header(...)) -> str:
    if x_api_key != settings.API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key
