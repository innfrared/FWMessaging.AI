from __future__ import annotations

from app.application.ports.llm import LLMPort
from app.domain.entities.intent import IntentClassification


class MockLLM(LLMPort):
    def classify_intent(self, text: str, language_hint: str | None) -> IntentClassification:
        normalized = text.lower()
        if any(word in normalized for word in ("facial", "blackhead")):
            intent = "pricing"
            service = "Facial + Deep Blackhead Removal"
        elif "laser" in normalized:
            intent = "pricing"
            service = "Laser Hair Removal"
        elif any(word in normalized for word in ("lamination", "lash")):
            intent = "promo_pricing"
            service = "Eyelash Lamination + Tinting"
        elif any(word in normalized for word in ("hours", "open", "hora", "horario")):
            intent = "hours"
            service = None
        elif any(word in normalized for word in ("location", "address", "direccion", "ubicacion")):
            intent = "location"
            service = None
        else:
            intent = "services_list"
            service = None

        language = "es" if any(word in normalized for word in ("hola", "gracias", "precio", "horario")) else "en"

        return IntentClassification(
            intent=intent,
            language=language,
            normalized_text=text,
            service=service,
        )
