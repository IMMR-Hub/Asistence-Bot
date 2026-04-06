from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.common import ClassificationResult, EntityExtractionResult
from app.services.llm_client import get_ollama_client, parse_llm_json

logger = get_logger(__name__)


class EntityExtractor:
    """
    Extracts structured fields from classification entities dict.
    The LLM already returns entities during classification;
    this module enriches and validates them — no additional LLM call needed
    unless entities are missing.
    """

    def extract_from_classification(
        self, classification: ClassificationResult
    ) -> EntityExtractionResult:
        entities = classification.entities or {}
        return EntityExtractionResult(
            customer_name=entities.get("customer_name") or None,
            product_or_service_interest=entities.get("product_or_service_interest") or None,
            budget_hint=entities.get("budget_hint") or None,
            location_hint=entities.get("location_hint") or None,
            preferred_contact_time=entities.get("preferred_contact_time") or None,
            language=entities.get("language") or None,
        )

    def merge_with_contact_data(
        self,
        extracted: EntityExtractionResult,
        contact_name: str | None,
        contact_phone: str | None,
        contact_email: str | None,
        language: str | None,
    ) -> EntityExtractionResult:
        """Fill in gaps from channel-level contact metadata."""
        return EntityExtractionResult(
            customer_name=extracted.customer_name or contact_name,
            product_or_service_interest=extracted.product_or_service_interest,
            budget_hint=extracted.budget_hint,
            location_hint=extracted.location_hint,
            preferred_contact_time=extracted.preferred_contact_time,
            language=extracted.language or language,
        )
