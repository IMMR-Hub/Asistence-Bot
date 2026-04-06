from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMBase, TimestampedModel


# ---- Config sub-schemas ----

class BusinessHours(BaseModel):
    monday_to_friday: str = "08:00-18:00"
    saturday: str = "08:00-12:00"
    sunday: str = "closed"


class FAQEntry(BaseModel):
    question: str
    answer: str


class EscalationRules(BaseModel):
    confidence_threshold: float = 0.72
    always_escalate_hot_leads: bool = False
    always_escalate_complaints: bool = True


class FollowUpRule(BaseModel):
    rule_key: str
    delay_minutes: int
    channel: str = "same_as_origin"
    enabled: bool = True


class ClassificationOverrides(BaseModel):
    hot_keywords: list[str] = []
    human_request_keywords: list[str] = [
        "quiero hablar con una persona", "necesito hablar con alguien", "quiero un humano",
        "quiero asesor", "quiero hablar con un asesor", "persona real", "agente humano"
    ]
    clinical_urgency_keywords: list[str] = [
        # Pain indicators
        "dolor", "me duele", "duele", "dolor de muela", "dolor fuerte", "dolor intenso",
        # Bleeding/emergency
        "sangrado", "sangrando", "sangra", "hemorragia",
        # Swelling/infection
        "hinchazón", "inflamado", "inflamación", "infección", "pus", "absceso",
        # Emergency indicators
        "emergencia", "urgencia", "urgente", "inmediato", "ahora", "pronto",
        # Trauma/accident
        "se me cayó", "me golpeé", "accidente", "fracturado", "roto", "golpe",
        # Fever/infection signs
        "fiebre", "infección", "infectado", "pus"
    ]


class TenantConfigSchema(BaseModel):
    """Full tenant configuration object stored as JSONB."""

    tenant_slug: str
    business_name: str
    timezone: str = "UTC"
    default_language: str = "es"
    enabled_channels: list[str] = ["whatsapp", "email"]
    enabled_modules: list[str] = []
    brand_tone: str = "professional"
    business_hours: BusinessHours = Field(default_factory=BusinessHours)
    faq_entries: list[FAQEntry] = []
    escalation_rules: EscalationRules = Field(default_factory=EscalationRules)
    follow_up_rules: list[FollowUpRule] = []
    classification_overrides: ClassificationOverrides = Field(
        default_factory=ClassificationOverrides
    )

    # Optional fields
    product_catalog_source: str | None = None
    crm_owner_name: str | None = None
    currency: str | None = None
    allowed_languages: list[str] = []
    signature_text: str | None = None
    whatsapp_number: str | None = None
    email_sender_name: str | None = None
    email_sender_address: str | None = None
    industry_tag: str | None = None
    custom_tags: list[str] = []
    knowledge_documents: list[str] = []

    # New fields for better responses
    initial_greeting: str | None = None  # Custom greeting instead of auto-detect
    empathy_instructions: str | None = None  # Special instructions for empathetic responses
    available_slots: list[str] = []  # Appointment slots to offer (e.g., ["mañana 10:00", "mañana 15:00"])
    emergency_contact_info: str | None = None  # Info to provide for true emergencies

    @field_validator("confidence_threshold", mode="before", check_fields=False)
    @classmethod
    def _noop(cls, v: Any) -> Any:
        return v


# ---- API request/response schemas ----

class TenantCreate(BaseModel):
    tenant_slug: str
    business_name: str
    timezone: str = "UTC"
    default_language: str = "es"
    industry_tag: str | None = None


class TenantRead(TimestampedModel):
    tenant_slug: str
    business_name: str
    status_active: bool
    timezone: str
    default_language: str
    industry_tag: str | None = None


class TenantConfigCreate(BaseModel):
    config: TenantConfigSchema


class TenantConfigRead(ORMBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    version: int
    is_active: bool
    config_json: dict[str, Any]
    created_at: Any
    updated_at: Any
