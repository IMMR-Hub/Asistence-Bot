from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.tenant import TenantConfigSchema


def test_valid_config_loads(sample_tenant_config_dict):
    config = TenantConfigSchema.model_validate(sample_tenant_config_dict)
    assert config.tenant_slug == "test-tenant"
    assert config.business_name == "Test Business"
    assert "whatsapp" in config.enabled_channels
    assert config.escalation_rules.confidence_threshold == 0.72
    assert config.escalation_rules.always_escalate_complaints is True


def test_faq_entries_parsed(sample_tenant_config_dict):
    config = TenantConfigSchema.model_validate(sample_tenant_config_dict)
    assert len(config.faq_entries) == 1
    assert config.faq_entries[0].question == "horario"


def test_follow_up_rules_parsed(sample_tenant_config_dict):
    config = TenantConfigSchema.model_validate(sample_tenant_config_dict)
    assert len(config.follow_up_rules) == 1
    rule = config.follow_up_rules[0]
    assert rule.rule_key == "warm_lead_no_reply"
    assert rule.delay_minutes == 120
    assert rule.enabled is True


def test_classification_overrides(sample_tenant_config_dict):
    config = TenantConfigSchema.model_validate(sample_tenant_config_dict)
    assert "comprar" in config.classification_overrides.hot_keywords
    assert "humano" in config.classification_overrides.human_request_keywords


def test_missing_required_field_raises():
    with pytest.raises(ValidationError):
        TenantConfigSchema.model_validate({"business_name": "Test"})  # missing tenant_slug


def test_defaults_applied():
    config = TenantConfigSchema.model_validate(
        {"tenant_slug": "x", "business_name": "Y"}
    )
    assert config.default_language == "es"
    assert config.timezone == "UTC"
    assert config.brand_tone == "professional"
    assert config.follow_up_rules == []
    assert config.faq_entries == []
