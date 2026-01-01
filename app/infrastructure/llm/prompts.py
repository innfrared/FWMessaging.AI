from enum import Enum

def build_generate_prompt(profile: dict, count: int, existing: list[str]) -> str:
    mode_raw = profile.get("mode", "conversation")
    if isinstance(mode_raw, Enum):
        mode = str(mode_raw.value).strip().lower()
    else:
        mode = str(mode_raw).strip().lower()

    mode_rules = {
        "conversation": "Progressive, interactive questions with follow-ups. Start broad then narrow.",
        "drilldown": "Deep dive into one topic at a time. Ask probing follow-ups that increase difficulty.",
        "case": "Scenario-based questions with constraints, tradeoffs, and real-world details.",
        "challenge": "Hard questions with edge cases, failure modes, tricky constraints, and gotchas.",
        "retrospective": "Project-based reflection: decisions, tradeoffs, lessons learned, and what you'd do differently.",
    }
    mode_instruction = mode_rules.get(mode, mode_rules["conversation"])

    role = (profile.get("role") or "").strip()
    level = (profile.get("level") or "").strip()
    stack = profile.get("stack") or []

    existing_preview = existing[:50]

    return (
        "You are an interview question generator.\n"
        "Return ONLY valid JSON. No markdown. No extra text.\n"
        "Output schema:\n"
        "  {\"questions\": [\"...\", \"...\", ...]}\n"
        "Rules:\n"
        f"  - Return EXACTLY {count} questions in the questions array.\n"
        "  - Each question must be unique (no duplicates or near-duplicates).\n"
        "  - Do NOT repeat or paraphrase any item from existing_questions.\n"
        "  - Questions must be specific and technical (avoid generic HR questions).\n"
        "  - Match the candidate context (role/level/stack) and the requested mode.\n"
        "  - Questions should be standalone (no references like “as discussed earlier”).\n"
        "  - No numbering like \"1.\" inside the strings.\n"
        "\n"
        "Candidate profile:\n"
        f"  role: {role}\n"
        f"  level: {level}\n"
        f"  stack: {stack}\n"
        f"  mode: {mode}\n"
        f"  mode_instruction: {mode_instruction}\n"
        "\n"
        f"existing_questions (avoid all of these): {existing_preview}\n"
    )

def build_evaluate_prompt(context: dict, items: list[dict], include_summary: bool) -> str:
    return (
        "You are an interview evaluator.\n"
        "Return ONLY valid JSON. No markdown. No extra text.\n"
        "\n"
        "You MUST follow this response schema exactly:\n"
        "{\n"
        "  \"results\": [\n"
        "    {\"order\": 1, \"score\": 0, \"feedback\": \"...\", \"meta\": {}},\n"
        "    {\"order\": 2, \"score\": 0, \"feedback\": \"...\", \"meta\": {}}\n"
        "  ],\n"
        f"  \"overall\": {'{\"score\": 0, \"feedback\": \"...\", \"meta\": {}}' if include_summary else 'null'}\n"
        "}\n"
        "\n"
        "Rules:\n"
        "  - results must contain EXACTLY one entry for each input item.\n"
        "  - Each result.order MUST match an input item.order.\n"
        "  - Do NOT add extra orders. Do NOT omit any order.\n"
        "  - score must be an integer from 0 to 10.\n"
        "  - feedback must be a concise string with actionable notes.\n"
        "  - meta must be a JSON object (dictionary). Never null.\n"
        + ("  - overall MUST be a JSON object (not null) when include_summary=true.\n" if include_summary else "  - overall MUST be null when include_summary=false.\n")
        "\n"
        f"Context: {context}\n"
        f"Items: {items}\n"
    )
