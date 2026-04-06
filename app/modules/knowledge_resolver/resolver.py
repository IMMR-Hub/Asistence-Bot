from __future__ import annotations

from app.schemas.tenant import FAQEntry, TenantConfigSchema
from app.core.logging import get_logger

logger = get_logger(__name__)


class KnowledgeContext:
    def __init__(
        self,
        business_name: str,
        brand_tone: str,
        business_hours_text: str,
        faq_snippets: str,
        signature_text: str | None,
        allowed_languages: list[str],
        knowledge_documents: list[str],
    ) -> None:
        self.business_name = business_name
        self.brand_tone = brand_tone
        self.business_hours_text = business_hours_text
        self.faq_snippets = faq_snippets
        self.signature_text = signature_text
        self.allowed_languages = allowed_languages
        self.knowledge_documents = knowledge_documents


class KnowledgeResolver:
    """
    Loads tenant knowledge, FAQs, product snippets, business rules, tone,
    and policies from the tenant config. No external vector DB required
    for the core; knowledge_documents are plain text snippets stored in config.
    """

    def resolve(self, config: TenantConfigSchema) -> KnowledgeContext:
        faq_text = self._build_faq_text(config.faq_entries)
        hours_text = self._build_hours_text(config)

        return KnowledgeContext(
            business_name=config.business_name,
            brand_tone=config.brand_tone,
            business_hours_text=hours_text,
            faq_snippets=faq_text,
            signature_text=config.signature_text,
            allowed_languages=config.allowed_languages or [config.default_language],
            knowledge_documents=config.knowledge_documents,
        )

    def _build_faq_text(self, entries: list[FAQEntry]) -> str:
        if not entries:
            return ""
        lines = ["Frequently Asked Questions:"]
        for e in entries:
            lines.append(f"Q: {e.question}")
            lines.append(f"A: {e.answer}")
        return "\n".join(lines)

    def _build_hours_text(self, config: TenantConfigSchema) -> str:
        h = config.business_hours
        return (
            f"Business hours: Mon-Fri {h.monday_to_friday}, "
            f"Saturday {h.saturday}, Sunday {h.sunday}"
        )
