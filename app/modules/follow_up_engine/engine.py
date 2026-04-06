from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import redis
from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.follow_up import FollowUpJob
from app.db.models.lead import Lead
from app.db.models.conversation import Conversation
from app.modules.audit_logger.logger import AuditLogger
from app.schemas.tenant import FollowUpRule, TenantConfigSchema

logger = get_logger(__name__)


class FollowUpEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogger(session)

    async def schedule_follow_ups(
        self,
        lead: Lead,
        conversation: Conversation,
        config: TenantConfigSchema,
    ) -> list[FollowUpJob]:
        jobs: list[FollowUpJob] = []
        now = datetime.now(timezone.utc)

        active_rules = [r for r in config.follow_up_rules if r.enabled]
        if not active_rules:
            return jobs

        for rule in active_rules:
            channel = (
                conversation.channel if rule.channel == "same_as_origin" else rule.channel
            )
            scheduled_for = now + timedelta(minutes=rule.delay_minutes)

            job = FollowUpJob(
                tenant_id=lead.tenant_id,
                lead_id=lead.id,
                conversation_id=conversation.id,
                channel=channel,
                status="pending",
                scheduled_for=scheduled_for,
                payload={
                    "rule_key": rule.rule_key,
                    "lead_temperature": lead.lead_temperature,
                    "intent": lead.intent,
                    "delay_minutes": rule.delay_minutes,
                },
            )
            self.session.add(job)
            await self.session.flush()
            await self.session.refresh(job)

            # Enqueue in RQ with countdown
            try:
                rq_job = self._enqueue_rq(job, rule)
                if rq_job:
                    job.rq_job_id = rq_job.id
                    await self.session.flush()
            except Exception as exc:
                logger.warning("rq_enqueue_failed", rule=rule.rule_key, error=str(exc))

            await self.audit.log(
                event_type="follow_up_scheduled",
                event_source="follow_up_engine",
                payload={
                    "follow_up_job_id": str(job.id),
                    "rule_key": rule.rule_key,
                    "scheduled_for": scheduled_for.isoformat(),
                    "channel": channel,
                },
                tenant_id=lead.tenant_id,
            )
            jobs.append(job)
            logger.info(
                "follow_up_scheduled",
                rule=rule.rule_key,
                scheduled_for=scheduled_for.isoformat(),
                lead_id=str(lead.id),
            )

        return jobs

    def _enqueue_rq(self, job: FollowUpJob, rule: FollowUpRule) -> object | None:
        try:
            conn = redis.from_url(settings.REDIS_URL)
            q = Queue(settings.RQ_QUEUE_NAME, connection=conn)
            delay_seconds = rule.delay_minutes * 60
            rq_job = q.enqueue_in(
                timedelta(seconds=delay_seconds),
                "app.workers.tasks.execute_follow_up",
                str(job.id),
            )
            return rq_job
        except Exception as exc:
            logger.warning("rq_not_available", error=str(exc))
            return None
