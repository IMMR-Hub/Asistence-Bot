from __future__ import annotations

"""
RQ task functions.
These run in the worker process — they must be importable at module level.
Each function receives the follow_up_job_id (str) and handles the full lifecycle.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def execute_follow_up(follow_up_job_id: str) -> None:
    """
    Execute a scheduled follow-up job.
    Fetches the job, generates follow-up text via LLM, and sends it.
    Marks job as sent or failed.
    """
    asyncio.run(_execute_follow_up_async(uuid.UUID(follow_up_job_id)))


async def _execute_follow_up_async(job_id: uuid.UUID) -> None:
    from app.db.session import AsyncSessionLocal
    from app.db.repositories.follow_up_repo import FollowUpRepository
    from app.db.repositories.lead_repo import LeadRepository
    from app.db.repositories.conversation_repo import ConversationRepository
    from app.db.repositories.contact_repo import ContactRepository
    from app.db.repositories.tenant_repo import TenantRepository
    from app.channels.whatsapp.adapter import send_whatsapp_message
    from app.channels.email.adapter import send_email
    from app.modules.audit_logger.logger import AuditLogger
    from app.services.llm_client import get_ollama_client, parse_llm_json
    from app.core.config import settings
    from app.schemas.tenant import TenantConfigSchema

    async with AsyncSessionLocal() as session:
        follow_up_repo = FollowUpRepository(session)
        job = await follow_up_repo.get_by_id(job_id)

        if not job:
            logger.error("follow_up_job_not_found", job_id=str(job_id))
            return

        if job.status != "pending":
            logger.info("follow_up_job_already_processed", job_id=str(job_id), status=job.status)
            return

        audit = AuditLogger(session)

        try:
            # Load related data
            lead_repo = LeadRepository(session)
            conv_repo = ConversationRepository(session)
            contact_repo = ContactRepository(session)
            tenant_repo = TenantRepository(session)

            lead = await lead_repo.get_by_id(job.lead_id)
            conv = await conv_repo.get_by_id(job.conversation_id)
            if not lead or not conv:
                raise ValueError("Lead or conversation not found")

            contact = await contact_repo.get_by_id(lead.contact_id)
            cfg_record = await tenant_repo.get_active_config(lead.tenant_id)
            if not cfg_record:
                raise ValueError("No active tenant config")

            config = TenantConfigSchema.model_validate(cfg_record.config_json)

            # Generate follow-up text
            text = await _generate_follow_up_text(lead, config, job.payload)

            # Send via appropriate channel
            sent = False
            if job.channel == "whatsapp":
                phone = contact.phone or contact.external_contact_id or "" if contact else ""
                if phone:
                    sent = await send_whatsapp_message(to_phone=phone, text=text)
            elif job.channel == "email":
                email = contact.email or "" if contact else ""
                if email:
                    sent = await send_email(
                        to_email=email,
                        subject="Seguimiento de tu consulta",
                        body=text,
                        from_name=config.email_sender_name,
                        from_email=config.email_sender_address,
                    )

            job.status = "sent" if sent else "failed"
            job.executed_at = datetime.now(timezone.utc)
            await session.flush()

            await audit.log(
                event_type="follow_up_executed",
                event_source="worker",
                payload={
                    "follow_up_job_id": str(job_id),
                    "sent": sent,
                    "channel": job.channel,
                },
                tenant_id=lead.tenant_id,
            )
            await session.commit()
            logger.info("follow_up_executed", job_id=str(job_id), sent=sent)

        except Exception as exc:
            job.status = "failed"
            job.executed_at = datetime.now(timezone.utc)
            await session.flush()
            await session.commit()
            logger.error("follow_up_failed", job_id=str(job_id), error=str(exc))


async def _generate_follow_up_text(lead: object, config: object, payload: dict) -> str:
    from app.services.llm_client import get_ollama_client, parse_llm_json, LLMError
    from app.core.config import settings

    client = get_ollama_client()
    rule_key = payload.get("rule_key", "")
    intent = payload.get("intent", "")
    temperature = payload.get("lead_temperature", "warm")

    prompt = f"""
Generate a short, friendly follow-up message for a {temperature} lead with intent: {intent}.
Business: {config.business_name}  # type: ignore[attr-defined]
Tone: {config.brand_tone}  # type: ignore[attr-defined]
Rule: {rule_key}
Language: {config.default_language}  # type: ignore[attr-defined]
Keep it under 3 sentences.
Respond with JSON: {{"follow_up_text": "..."}}
""".strip()

    try:
        raw = await client.generate(
            model=settings.OLLAMA_FALLBACK_MODEL,
            prompt=prompt,
            temperature=0.5,
            expect_json=True,
        )
        parsed = parse_llm_json(raw)
        return parsed.get("follow_up_text", "")
    except LLMError:
        # Graceful degradation: return a generic follow-up
        return f"Hola, ¿puedo ayudarte con tu consulta? Estamos disponibles para asistirte."
