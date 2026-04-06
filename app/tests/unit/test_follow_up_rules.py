from __future__ import annotations

from app.schemas.tenant import FollowUpRule, TenantConfigSchema


def test_follow_up_rules_enabled_filtering():
    config = TenantConfigSchema.model_validate({
        "tenant_slug": "x",
        "business_name": "X",
        "follow_up_rules": [
            {"rule_key": "rule_a", "delay_minutes": 60, "enabled": True},
            {"rule_key": "rule_b", "delay_minutes": 120, "enabled": False},
            {"rule_key": "rule_c", "delay_minutes": 1440, "enabled": True},
        ],
    })
    active = [r for r in config.follow_up_rules if r.enabled]
    assert len(active) == 2
    assert active[0].rule_key == "rule_a"
    assert active[1].rule_key == "rule_c"


def test_follow_up_channel_same_as_origin():
    rule = FollowUpRule(
        rule_key="test",
        delay_minutes=60,
        channel="same_as_origin",
        enabled=True,
    )
    assert rule.channel == "same_as_origin"


def test_follow_up_delay_calculation():
    from datetime import timedelta

    rule = FollowUpRule(rule_key="x", delay_minutes=120, enabled=True)
    delta = timedelta(minutes=rule.delay_minutes)
    assert delta.total_seconds() == 7200


def test_empty_follow_up_rules():
    config = TenantConfigSchema.model_validate({"tenant_slug": "x", "business_name": "X"})
    assert config.follow_up_rules == []
    active = [r for r in config.follow_up_rules if r.enabled]
    assert active == []
