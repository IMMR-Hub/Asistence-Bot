from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.common import ClassificationResult, NormalizedMessage
from app.schemas.tenant import TenantConfigSchema
from app.services.llm_client import LLMError, get_llm_client, parse_llm_json

logger = get_logger(__name__)

VALID_INTENTS = {
    "product_inquiry", "pricing_request", "availability_check",
    "appointment_request", "quote_request", "support_request",
    "complaint", "follow_up_reply", "unknown",
}
VALID_TEMPERATURES = {"hot", "warm", "cold", "unqualified"}
VALID_URGENCIES = {"high", "medium", "low"}

CLASSIFICATION_SYSTEM = """You are a sales lead classification engine.
Respond ONLY with valid JSON matching the schema provided.
Never fabricate pricing or availability data.
Never include personal opinions."""

CLASSIFICATION_PROMPT_TEMPLATE = """
Classify the following customer message for business: {business_name} ({industry}).

Message:
\"\"\"
{message_text}
\"\"\"

Known hot keywords (may indicate hot lead): {hot_keywords}
Known human-request keywords: {human_request_keywords}
Known clinical urgency keywords (pain, bleeding, emergency): {clinical_urgency_keywords}
Default language: {default_language}

IMPORTANT RULES:
- If message contains clinical urgency keywords (pain, sangrado, hinchazón, emergencia, urgencia), set clinical_urgency=true
- If message contains human-request keywords (quiero hablar, persona, humano, asesor), set customer_requests_human=true
- Classify intent based on commercial intent, NOT on urgency level
- clinical_urgency and customer_requests_human are separate from intent

Return JSON with exactly these fields:
{{
  "intent": one of {valid_intents},
  "lead_temperature": one of {valid_temperatures},
  "urgency": one of {valid_urgencies},
  "confidence": float 0.0-1.0,
  "summary": short one-sentence summary in {default_language},
  "customer_requests_human": boolean,
  "clinical_urgency": boolean,
  "entities": {{
    "customer_name": string or null,
    "product_or_service_interest": string or null,
    "budget_hint": string or null,
    "location_hint": string or null,
    "preferred_contact_time": string or null,
    "language": string or null
  }}
}}
""".strip()


class IntentClassifier:
    def __init__(self) -> None:
        self.client = get_llm_client()
        self.model = settings.LLM_CLASSIFY_MODEL
        self.fallback_model = settings.LLM_CLASSIFY_MODEL  # Use same model, differ by temperature

    def _apply_keyword_overrides(
        self,
        result: ClassificationResult,
        text: str,
        config: TenantConfigSchema,
    ) -> ClassificationResult:
        overrides = config.classification_overrides
        text_lower = text.lower()

        # Note: LLM should already set customer_requests_human and clinical_urgency in JSON
        # This method applies additional overrides/reinforcement

        # Human-request keywords → ensure flag is set
        if not result.customer_requests_human:
            for kw in overrides.human_request_keywords:
                if kw.lower() in text_lower:
                    result.customer_requests_human = True
                    logger.debug("human_request_keyword_matched", keyword=kw)
                    break

        # Clinical urgency keywords → ensure flag is set
        if not result.clinical_urgency:
            for kw in overrides.clinical_urgency_keywords:
                if kw.lower() in text_lower:
                    result.clinical_urgency = True
                    logger.debug("clinical_urgency_keyword_matched", keyword=kw)
                    break

        # Hot keywords → promote temperature if not already hot
        for kw in overrides.hot_keywords:
            if kw.lower() in text_lower:
                if result.lead_temperature not in ("hot",):
                    result.lead_temperature = "hot"
                    logger.debug("hot_keyword_override", keyword=kw)
                break

        return result

    async def classify(
        self,
        message: NormalizedMessage,
        config: TenantConfigSchema,
    ) -> ClassificationResult:
        text = message.text_content or ""

        prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(
            business_name=config.business_name,
            industry=config.industry_tag or "general",
            message_text=text[:2000],
            hot_keywords=json.dumps(config.classification_overrides.hot_keywords),
            human_request_keywords=json.dumps(config.classification_overrides.human_request_keywords),
            clinical_urgency_keywords=json.dumps(config.classification_overrides.clinical_urgency_keywords),
            default_language=config.default_language,
            valid_intents=json.dumps(sorted(VALID_INTENTS)),
            valid_temperatures=json.dumps(sorted(VALID_TEMPERATURES)),
            valid_urgencies=json.dumps(sorted(VALID_URGENCIES)),
        )

        raw: str = ""
        model_used = self.model
        try:
            raw = await self.client.generate(
                model=self.model,
                prompt=prompt,
                system=CLASSIFICATION_SYSTEM,
                temperature=0.1,
                expect_json=True,
            )
        except LLMError:
            logger.warning("primary_model_failed_falling_back", model=self.model)
            model_used = self.fallback_model
            raw = await self.client.generate(
                model=self.fallback_model,
                prompt=prompt,
                system=CLASSIFICATION_SYSTEM,
                temperature=0.1,
                expect_json=True,
            )

        parsed = parse_llm_json(raw)
        result = self._build_result(parsed, model_used)
        result = self._apply_keyword_overrides(result, text, config)

        logger.info(
            "message_classified",
            intent=result.intent,
            temperature=result.lead_temperature,
            confidence=result.confidence,
            model=model_used,
            tenant_id=str(message.tenant_id),
        )
        return result

    def _build_result(self, parsed: dict[str, Any], model_name: str) -> ClassificationResult:
        intent = parsed.get("intent", "unknown")
        if intent not in VALID_INTENTS:
            intent = "unknown"

        temperature = parsed.get("lead_temperature", "cold")
        if temperature not in VALID_TEMPERATURES:
            temperature = "cold"

        urgency = parsed.get("urgency", "low")
        if urgency not in VALID_URGENCIES:
            urgency = "low"

        raw_conf = parsed.get("confidence", 0.5)
        try:
            confidence = max(0.0, min(1.0, float(raw_conf)))
        except (TypeError, ValueError):
            confidence = 0.5

        return ClassificationResult(
            intent=intent,
            lead_temperature=temperature,
            urgency=urgency,
            confidence=confidence,
            summary=str(parsed.get("summary", "")),
            entities=parsed.get("entities", {}),
            customer_requests_human=parsed.get("customer_requests_human", False),
            clinical_urgency=parsed.get("clinical_urgency", False),
        )
