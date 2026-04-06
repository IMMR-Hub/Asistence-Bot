from __future__ import annotations

import pytest

from app.modules.human_escalation.escalation import (
    ESCALATION_REASON_COMPLAINT,
    ESCALATION_REASON_HOT_LEAD_POLICY,
    ESCALATION_REASON_HUMAN_REQUESTED,
    ESCALATION_REASON_LOW_CONFIDENCE,
    HumanEscalation,
)
from app.schemas.common import ClassificationResult
from app.schemas.tenant import EscalationRules, TenantConfigSchema


def _make_classification(**kwargs) -> ClassificationResult:
    defaults = {
        "intent": "product_inquiry",
        "lead_temperature": "warm",
        "urgency": "medium",
        "confidence": 0.85,
        "summary": "test",
        "entities": {},
    }
    defaults.update(kwargs)
    return ClassificationResult(**defaults)


def _make_config(rules: dict | None = None) -> TenantConfigSchema:
    base = {
        "tenant_slug": "test",
        "business_name": "Test",
        "escalation_rules": rules or {
            "confidence_threshold": 0.72,
            "always_escalate_hot_leads": False,
            "always_escalate_complaints": True,
        },
    }
    return TenantConfigSchema.model_validate(base)


def test_no_escalation_above_threshold():
    cls = _make_classification(confidence=0.9)
    config = _make_config()
    # We test the evaluate method without a DB session
    module = HumanEscalation.__new__(HumanEscalation)
    decision = module.evaluate(cls, config)
    assert decision.should_escalate is False


def test_escalate_below_threshold():
    cls = _make_classification(confidence=0.5)
    config = _make_config()
    module = HumanEscalation.__new__(HumanEscalation)
    decision = module.evaluate(cls, config)
    assert decision.should_escalate is True
    assert decision.reason == ESCALATION_REASON_LOW_CONFIDENCE


def test_escalate_exactly_at_threshold():
    # threshold=0.72, confidence=0.72 → NOT below, so no escalation
    cls = _make_classification(confidence=0.72)
    config = _make_config()
    module = HumanEscalation.__new__(HumanEscalation)
    decision = module.evaluate(cls, config)
    assert decision.should_escalate is False


def test_escalate_complaint_always():
    cls = _make_classification(intent="complaint", confidence=0.95)
    config = _make_config()
    module = HumanEscalation.__new__(HumanEscalation)
    decision = module.evaluate(cls, config)
    assert decision.should_escalate is True
    assert decision.reason == ESCALATION_REASON_COMPLAINT


def test_no_escalate_complaint_when_disabled():
    cls = _make_classification(intent="complaint", confidence=0.95)
    config = _make_config({
        "confidence_threshold": 0.72,
        "always_escalate_hot_leads": False,
        "always_escalate_complaints": False,
    })
    module = HumanEscalation.__new__(HumanEscalation)
    decision = module.evaluate(cls, config)
    assert decision.should_escalate is False


def test_escalate_human_requested():
    cls = _make_classification(
        confidence=0.9,
        entities={"_human_requested": True},
    )
    config = _make_config()
    module = HumanEscalation.__new__(HumanEscalation)
    decision = module.evaluate(cls, config)
    assert decision.should_escalate is True
    assert decision.reason == ESCALATION_REASON_HUMAN_REQUESTED


def test_escalate_hot_lead_when_policy_enabled():
    cls = _make_classification(lead_temperature="hot", confidence=0.9)
    config = _make_config({
        "confidence_threshold": 0.72,
        "always_escalate_hot_leads": True,
        "always_escalate_complaints": False,
    })
    module = HumanEscalation.__new__(HumanEscalation)
    decision = module.evaluate(cls, config)
    assert decision.should_escalate is True
    assert decision.reason == ESCALATION_REASON_HOT_LEAD_POLICY
