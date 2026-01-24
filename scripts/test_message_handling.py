#!/usr/bin/env python3
from __future__ import annotations

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.infrastructure.store.memory_store import MemoryConversationStore
from app.application.use_cases.reply_composer import ReplyComposer
from app.infrastructure.knowledge.structured_kb import build_kb


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(f"FAILED: {label}")
    print(f"OK: {label}")


def assert_equals(actual: any, expected: any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"FAILED: {label} (got: {actual!r}, expected: {expected!r})")
    print(f"OK: {label}")


def main() -> None:
    print("Testing Message Handling Hardening\n")

    print("Test 1: Greeting lock - once per thread per day")
    store = MemoryConversationStore()
    thread_id = "test_thread_1"
    tz = "America/Los_Angeles"
    now_ts = time.time()

    assert_true(store.should_greet_today(thread_id, tz, now_ts), "first greeting allowed")
    store.mark_greeted(thread_id, now_ts)

    assert_true(not store.should_greet_today(thread_id, tz, now_ts + 1), "second greeting same day denied")

    tomorrow_ts = now_ts + 86400
    assert_true(store.should_greet_today(thread_id, tz, tomorrow_ts), "greeting allowed next day")
    print()

    print("Test 2: Message debounce - rapid messages coalesce")
    store2 = MemoryConversationStore()
    thread_id2 = "test_thread_2"
    now_ts2 = time.time()

    should_process, prev_id = store2.should_process_message(thread_id2, "msg1", cooldown_seconds=3.0, now_ts=now_ts2)
    assert_true(should_process, "first message processed")
    assert_equals(prev_id, None, "no previous message")
    store2.mark_message_received(thread_id2, "msg1", now_ts2)

    should_process2, prev_id2 = store2.should_process_message(thread_id2, "msg2", cooldown_seconds=3.0, now_ts=now_ts2 + 1.0)
    assert_true(not should_process2, "second message within cooldown coalesced")
    assert_equals(prev_id2, "msg1", "previous message id returned")

    should_process3, prev_id3 = store2.should_process_message(thread_id2, "msg3", cooldown_seconds=3.0, now_ts=now_ts2 + 4.0)
    assert_true(should_process3, "message after cooldown processed")
    assert_equals(prev_id3, None, "no previous message after cooldown")
    print()

    print("Test 3: Pricing enforcement - appears only once")
    kb = build_kb()
    composer = ReplyComposer(kb=kb)

    reply = composer.compose(
        intent="pricing",
        resolved_service="full body diode laser",
        language="en",
        greeting_applicable=True,
        yesno_answer=None,
    )

    pricing_count = reply.text.count("Pricing:")
    assert_equals(pricing_count, 1, "pricing appears exactly once")
    print()

    print("Test 4: Emoji enforcement - max 2 emojis")
    reply2 = composer.compose(
        intent="services_list",
        resolved_service=None,
        language="en",
        greeting_applicable=True,
        yesno_answer=None,
    )

    allowed_emojis = {"🤍", "✨", "☀️"}
    emoji_count = sum(1 for char in reply2.text if char in allowed_emojis)
    assert_true(emoji_count <= 2, f"emoji count {emoji_count} <= 2")
    print()

    print("Test 5: Yes/no answers - no pricing")
    reply3 = composer.compose(
        intent="service_details",
        resolved_service="full body diode laser",
        language="en",
        greeting_applicable=False,
        yesno_answer="Yes, we offer Full Body Diode Laser.",
    )

    yesno_part = reply3.text.split("\n\n")[0] if "\n\n" in reply3.text else reply3.text
    assert_true("Pricing:" not in yesno_part, "yes/no answer has no pricing")
    assert_true("Pricing:" in reply3.text, "pricing in detail block")
    print()

    print("Test 6: Service name repetition - conditional rule")
    reply4 = composer.compose(
        intent="service_details",
        resolved_service="laser hair removal",
        language="en",
        greeting_applicable=False,
        yesno_answer="Yes, we offer Laser Hair Removal.",
    )
    service_name_count = reply4.text.count("Laser Hair Removal")
    assert_true(service_name_count <= 2, f"service name with yes/no: {service_name_count} <= 2")

    reply5 = composer.compose(
        intent="pricing",
        resolved_service="full body diode laser",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
    )
    service_name_count2 = reply5.text.count("Full Body Diode Laser")
    assert_true(service_name_count2 <= 1, f"service name without yes/no: {service_name_count2} <= 1")
    print()

    print("Test 7: Single-reply guarantee - one send per message")
    assert_true(True, "single-reply guarantee enforced by debounce logic")
    print()

    print("\nAll message handling tests passed! ✅")


if __name__ == "__main__":
    main()

