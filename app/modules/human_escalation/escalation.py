from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.escalation import Escalation
from app.db.repositories.escalation_repo import EscalationRepository
from app.modules.audit_logger.logger import AuditLogger
from app.schemas.common import ClassificationResult, NormalizedMessage
from app.schemas.tenant import TenantConfigSchema
from app.core.logging import get_logger

logger = get_logger(__name__)

ESCALATION_REASON_LOW_CONFIDENCE = "confidence_below_threshold"
ESCALATION_REASON_COMPLAINT = "complaint_intent"
ESCALATION_REASON_HUMAN_REQUESTED = "customer_requests_human"
ESCALATION_REASON_HOT_LEAD_POLICY = "hot_lead_requires_human"
ESCALATION_REASON_CLINICAL_URGENCY = "clinical_urgency_detected"


class EscalationDecision:
    def __init__(self, should_escalate: bool, reason: str | None = None) -> None:
        self.should_escalate = should_escalate
        self.reason = reason


class HumanEscalation:
    """
    Evaluates escalation rules and creates Escalation records.
    Does NOT send notifications — that is a separate concern.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.repo = EscalationRepository(session)
        self.audit = AuditLogger(session)

    def evaluate(
        self,
        classification: ClassificationResult,
        config: TenantConfigSchema,
    ) -> EscalationDecision:
        rules = config.escalation_rules
        threshold = rules.confidence_threshold

        # Clinical urgency (pain, bleeding, medical emergency) — HIGHEST PRIORITY
        if classification.clinical_urgency:
            return EscalationDecision(True, ESCALATION_REASON_CLINICAL_URGENCY)

        # Always-escalate complaint
        if rules.always_escalate_complaints and classification.intent == "complaint":
            return EscalationDecision(True, ESCALATION_REASON_COMPLAINT)

        # Customer explicitly requested human
        if classification.customer_requests_human:
            return EscalationDecision(True, ESCALATION_REASON_HUMAN_REQUESTED)

        # Confidence below threshold
        if classification.confidence < threshold:
            return EscalationDecision(True, ESCALATION_REASON_LOW_CONFIDENCE)

        # Hot lead + policy requires human
        if (
            rules.always_escalate_hot_leads
            and classification.lead_temperature == "hot"
        ):
            return EscalationDecision(True, ESCALATION_REASON_HOT_LEAD_POLICY)

        return EscalationDecision(False)

    async def create_escalation(
        self,
        tenant_id: uuid.UUID,
        conversation_id: uuid.UUID,
        lead_id: uuid.UUID | None,
        reason: str,
        summary: str | None,
    ) -> Escalation:
        escalation = Escalation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            lead_id=lead_id,
            reason=reason,
            status="open",
            summary_text=summary,
        )
        self.repo.session.add(escalation)
        await self.repo.session.flush()
        await self.repo.session.refresh(escalation)

        await self.audit.log(
            event_type="escalation_created",
            event_source="human_escalation",
            payload={
                "escalation_id": str(escalation.id),
                "reason": reason,
                "conversation_id": str(conversation_id),
            },
            tenant_id=tenant_id,
        )
        logger.info(
            "escalation_created",
            escalation_id=str(escalation.id),
            reason=reason,
            tenant_id=str(tenant_id),
        )
        return escalation
