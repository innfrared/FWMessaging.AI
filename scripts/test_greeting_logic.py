#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.application.utils.greeting import build_greeting, is_follow_up
from app.infrastructure.store.memory_store import MemoryConversationStore


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(f"FAILED: {label}")
    print(f"OK: {label}")


def to_ts(dt: datetime) -> float:
    return dt.timestamp()


def main() -> None:
    store = MemoryConversationStore()
    tz = "America/Los_Angeles"
    thread = "user_1"

    assert_true(store.is_first_outbound_message_today(thread, tz), "first outbound is true")

    assert_true(store.is_first_outbound_message_today(thread, tz), "send failure keeps greeting allowed")

    store.mark_outbound(thread, time.time())
    assert_true(not store.is_first_outbound_message_today(thread, tz), "second outbound same day is false")

    la = ZoneInfo(tz)
    before_midnight = datetime(2024, 6, 1, 23, 59, tzinfo=la)
    after_midnight = datetime(2024, 6, 2, 0, 1, tzinfo=la)

    store.mark_outbound(thread, to_ts(before_midnight))
    assert_true(
        not store.is_first_outbound_message_today(thread, tz, now_ts=to_ts(before_midnight)),
        "still same day before midnight",
    )
    assert_true(
        store.is_first_outbound_message_today(thread, tz, now_ts=to_ts(after_midnight)),
        "new day after midnight LA time",
    )

    assert_true(build_greeting("en") == "Hi love, thank you for reaching out 💕", "english greeting")
    assert_true(build_greeting("es") == "Hola, gracias por comunicarte 💕", "spanish greeting")

    for msg in ["thanks", "thank you", "ok", "okay", "yes", "yep", "👍", "🙏"]:
        assert_true(is_follow_up(msg) is True, f"follow-up ack: {msg}")

    assert_true(is_follow_up("What are your hours?") is False, "non-ack question")


if __name__ == "__main__":
    main()
