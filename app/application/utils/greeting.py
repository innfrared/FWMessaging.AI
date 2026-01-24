from __future__ import annotations


def build_greeting(language: str) -> str:
    return "Hello, thank you for reaching out!"


def is_follow_up(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    ack_set = {
        "thanks",
        "thank you",
        "ok",
        "okay",
        "yes",
        "yep",
        "👍",
        "🙏",
    }
    return normalized in ack_set
