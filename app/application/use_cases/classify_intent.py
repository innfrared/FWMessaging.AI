from __future__ import annotations

from app.application.ports.llm import LLMPort
from app.domain.entities.intent import IntentClassification


class ClassifyIntentUseCase:
    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    def execute(self, text: str, language_hint: str | None = None) -> IntentClassification:
        return self._llm.classify_intent(text=text, language_hint=language_hint)
