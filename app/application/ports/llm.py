from abc import ABC, abstractmethod

from app.domain.entities.intent import IntentClassification


class LLMPort(ABC):
    @abstractmethod
    def classify_intent(
        self,
        text: str,
        language_hint: str | None,
    ) -> IntentClassification:
        raise NotImplementedError
