from dataclasses import dataclass


@dataclass(frozen=True)
class IntentClassification:
    intent: str
    language: str
    normalized_text: str
    service: str | None = None
