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
    base = (
        "You are an interview evaluator.\n"
        "Evaluate the following interview answers strictly.\n\n"
        f"Context:\n{context}\n\n"
        f"Items:\n{items}\n\n"
        "For each item, return:\n"
        "- order (int)\n"
        "- score (0-10)\n"
        "- feedback (string)\n"
        "- meta (object)\n\n"
    )

    if include_summary:
        base += (
            "Also return an overall summary with:\n"
            "- score (0-10)\n"
            "- feedback (string)\n"
            "- meta (object)\n\n"
        )

    base += "Return STRICT JSON matching the schema exactly."

    return base
