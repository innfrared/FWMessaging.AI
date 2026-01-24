from __future__ import annotations

ALLOWED_INTENTS = [
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
]


def build_intent_prompt(text: str) -> list[dict[str, str]]:
    system = (
        "You are an intent classifier for a beauty services business.\n"
        "Return ONLY valid JSON. No markdown. No extra text.\n"
        "Allowed intents:\n"
        f"{ALLOWED_INTENTS}\n"
        "Output schema:\n"
        "{\n"
        '  \"language\": \"en\" | \"es\",\n'
        '  \"intent\": \"...\",\n'
        '  \"service\": \"...\" | null,\n'
        '  \"normalized_text\": \"...\"\n'
        "}\n"
        "Rules:\n"
        "- Detect language (en/es).\n"
        "- normalized_text must be an English translation of the user message.\n"
        "- If unsure or out of business scope, set intent=out_of_scope.\n"
        "- service should be a specific service name when relevant (e.g., Laser Hair Removal).\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
