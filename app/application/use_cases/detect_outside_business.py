from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.response_template import ResponseTemplate


ALLOWED_INTENTS = {
    "services_list",
    "pricing",
    "promo_pricing",
    "service_details",
    "location",
    "hours",
    "availability",
    "booking",
    "equipment",
    "eligibility",
    "closing",
    "out_of_scope",
}


@dataclass(frozen=True)
class OutsideBusinessDecision:
    should_handoff: bool
    reason: str


def evaluate_outside_business(intent: str, template: ResponseTemplate | None) -> OutsideBusinessDecision:
    if intent not in ALLOWED_INTENTS:
        return OutsideBusinessDecision(True, "unknown_intent")
    if intent == "out_of_scope":
        return OutsideBusinessDecision(True, "out_of_scope")
    if template is None:
        return OutsideBusinessDecision(True, "missing_kb")
    return OutsideBusinessDecision(False, "")
