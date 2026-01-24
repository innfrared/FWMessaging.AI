from __future__ import annotations

import json
from typing import Any

from app.application.exceptions import LLMContractError
from app.application.ports.llm import LLMPort
from app.core.config import settings
from app.domain.entities.intent import IntentClassification
from app.infrastructure.llm.openai_client import OpenAIClient
from app.infrastructure.llm.prompts import build_intent_prompt


class OpenAILLM(LLMPort):
    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAILLM.")
        self.client = OpenAIClient(api_key=settings.OPENAI_API_KEY)

    def classify_intent(self, text: str, language_hint: str | None) -> IntentClassification:
        messages = build_intent_prompt(text)
        if language_hint:
            messages.append({"role": "system", "content": f"Language hint: {language_hint}"})

        raw = self.client.chat_json(
            model=settings.OPENAI_MODEL_CLASSIFY,
            messages=messages,
            temperature=settings.OPENAI_TEMPERATURE_CLASSIFY,
            max_tokens=300,
        )
        data = _parse_json(raw, what="intent")
        if not isinstance(data, dict):
            raise LLMContractError("Intent: expected JSON object.")

        intent = str(data.get("intent", "")).strip()
        language = str(data.get("language", "en")).strip().lower()
        normalized_text = str(data.get("normalized_text", "")).strip()
        service_raw = data.get("service")
        service = str(service_raw).strip() if service_raw else None

        if not intent or not normalized_text:
            raise LLMContractError("Intent: missing required fields.")

        return IntentClassification(
            intent=intent,
            language=language,
            normalized_text=normalized_text,
            service=service,
        )


def _parse_json(text: str, what: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        snippet = text[:200].replace("\n", " ")
        raise LLMContractError(f"{what.capitalize()}: invalid JSON. Snippet: {snippet!r}")
