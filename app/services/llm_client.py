from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMError(Exception):
    pass


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.timeout = settings.OLLAMA_TIMEOUT

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        expect_json: bool = True,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if expect_json:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise LLMError(f"Ollama HTTP error: {exc.response.status_code}") from exc
            except httpx.RequestError as exc:
                raise LLMError(f"Ollama connection error: {exc}") from exc

        data = resp.json()
        return data.get("response", "")

    async def health_check(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
            except Exception:
                return False


class TogetherAIClient:
    """OpenAI-compatible client for Together.ai API (2-4s response time)."""

    def __init__(self) -> None:
        self.api_key = settings.TOGETHER_API_KEY_OPTIONAL
        if not self.api_key:
            raise LLMError("TOGETHER_API_KEY_OPTIONAL must be set")
        self.base_url = "https://api.together.xyz/v1"
        self.timeout = 60

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        expect_json: bool = True,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise LLMError(f"Together.ai HTTP error: {exc.response.status_code}") from exc
            except httpx.RequestError as exc:
                raise LLMError(f"Together.ai connection error: {exc}") from exc

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            logger.warning("together_ai_empty_choices", model=model)
            return ""
        content = choices[0].get("message", {}).get("content", "")
        return content

    async def health_check(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
            except Exception:
                return False


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Extract first valid JSON object from LLM output, even if surrounded by prose."""
    raw = raw.strip()
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try finding JSON block via regex
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise LLMError(f"Cannot parse JSON from LLM output: {raw[:300]}")


class GenericOpenAIClient:
    """OpenAI-compatible client for Groq, Together.ai, and other providers."""

    def __init__(self) -> None:
        self.api_key = settings.LLM_API_KEY
        if not self.api_key:
            raise LLMError("LLM_API_KEY must be set")
        self.base_url = settings.LLM_API_BASE.rstrip("/")
        self.timeout = settings.LLM_TIMEOUT

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        expect_json: bool = True,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                error_detail = exc.response.text if exc.response else "No response body"
                logger.error(
                    "llm_http_error",
                    status=exc.response.status_code,
                    detail=error_detail[:200],
                )
                raise LLMError(f"OpenAI-compatible LLM HTTP {exc.response.status_code}: {error_detail[:200]}") from exc
            except httpx.RequestError as exc:
                logger.error("llm_connection_error", error=str(exc))
                raise LLMError(f"OpenAI-compatible LLM connection error: {exc}") from exc

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            logger.warning("llm_empty_choices", model=model)
            return ""
        content = choices[0].get("message", {}).get("content", "")
        return content

    async def health_check(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
            except Exception as exc:
                logger.error("llm_health_check_failed", error=str(exc))
                return False


_ollama_client: OllamaClient | None = None
_openai_compatible_client: GenericOpenAIClient | None = None


def get_ollama_client() -> OllamaClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client


def get_llm_client() -> GenericOpenAIClient | OllamaClient:
    """Factory: returns the configured LLM client with fallback support."""
    global _openai_compatible_client

    # Primary provider
    if settings.LLM_PROVIDER == "groq":
        if _openai_compatible_client is None:
            _openai_compatible_client = GenericOpenAIClient()
        return _openai_compatible_client

    # Fallback to Ollama
    if settings.LLM_FALLBACK_PROVIDER == "ollama":
        return get_ollama_client()

    raise LLMError(f"No LLM provider configured: {settings.LLM_PROVIDER}")
