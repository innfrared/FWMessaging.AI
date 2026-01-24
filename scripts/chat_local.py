from __future__ import annotations

#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.domain.entities.message import Message

"""
Interactive local chat harness (no HTTP, no Instagram).

Usage:
  python3 scripts/chat_local.py

What it does:
- Keeps a stable thread_id for the session
- Sends your typed messages through the same HandleIncomingMessageUseCase
- Prints decision details (intent, language, greeting applied, handoff) and the reply text
"""

import os
import sys
import time
from dataclasses import asdict
from typing import Any, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


def _safe_get(d: Any, *keys: str, default: Any = None) -> Any:
    """Try multiple keys in dict-like objects safely."""
    if d is None:
        return default
    if isinstance(d, dict):
        for k in keys:
            if k in d:
                return d[k]
        return default
    # dataclass / pydantic-ish
    for k in keys:
        if hasattr(d, k):
            return getattr(d, k)
    return default


def _print_header(thread_id: str) -> None:
    print("\nLocal Chat Harness")
    print("-" * 60)
    print(f"thread_id: {thread_id}")
    print("Type your message and press Enter.")
    print("Commands: /new (new thread), /quit, /help")
    print("-" * 60)


def _build_use_case():
    """
    Prefer using your project wiring if present.
    Fallback: construct minimal dependencies manually.
    """
    try:
        from app.wiring.dependencies import (  # type: ignore
            get_container,
        )

        container = get_container()
        return container
    except Exception as e:
        raise RuntimeError(
            "Could not construct HandleIncomingMessageUseCase via wiring.\n"
            "Fix by updating _build_use_case() imports to match your project.\n"
            f"Original error: {e}"
        ) from e


def main() -> None:
    # Stable session thread id; can override via env or /new
    thread_id = os.getenv("CHAT_THREAD_ID", "local_user_1")
    container = _build_use_case()
    use_case = container["use_case"]
    store = container["store"]
    _print_header(thread_id)

    while True:
        try:
            user_text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            return

        if not user_text:
            continue

        cmd = user_text.lower()
        if cmd in ("/quit", "/exit"):
            print("Bye!")
            return
        if cmd == "/help":
            print("Commands:")
            print("  /new  -> start a new thread_id (resets 'first message today' behavior)")
            print("  /history -> show last 10 messages")
            print("  /quit -> exit")
            continue
        if cmd == "/new":
            thread_id = f"local_user_{int(time.time())}"
            print(f"New thread_id: {thread_id}")
            continue
        if cmd == "/history":
            history = store.get_history(thread_id)
            print("\n--- History (last 10) ---")
            for item in history[-10:]:
                role = item.get("role")
                content = item.get("content", "")
                print(f"{role}: {content}")
            continue

        message = Message(
            id=f"local_{int(time.time()*1000)}",
            thread_id=thread_id,
            sender_id=thread_id,
            text=user_text,
            timestamp=int(time.time()),
            platform="local",
        )

        result: Optional[Any] = None
        call_errors = []

        if hasattr(use_case, "handle"):
            try:
                result = use_case.handle(message)  # type: ignore
            except Exception as e:
                call_errors.append(f"handle(message) Error: {e}")
        elif callable(use_case):
            try:
                result = use_case(message)  # type: ignore
            except Exception as e:
                call_errors.append(f"call(message) Error: {e}")
        elif hasattr(use_case, "execute"):
            try:
                result = use_case.execute(message)  # type: ignore
            except Exception as e:
                call_errors.append(f"execute(message) Error: {e}")

        if result is None and not call_errors:
            # Handle use case returns None on success.
            history = store.get_history(thread_id)
            last_item = next((item for item in reversed(history)), None)
            if last_item and last_item.get("role") == "assistant" and last_item.get("content"):
                print(f"(assistant) {last_item['content']}")
            elif last_item and last_item.get("role") == "system" and last_item.get("content"):
                print(f"(system) {last_item['content']}")
            else:
                print("(no outbound message)")
            continue
        if result is None:
            print("ERROR: Could not call use case.")
            for err in call_errors[-5:]:
                print(" -", err)
            continue

        # Normalize result for printing
        res_dict: dict[str, Any]
        if isinstance(result, dict):
            res_dict = result
        else:
            try:
                res_dict = asdict(result)  # dataclass
            except Exception:
                # pydantic or custom object
                res_dict = getattr(result, "dict", lambda: {})() or result.__dict__  # type: ignore

        should_handoff = bool(_safe_get(res_dict, "should_handoff", "handoff", default=False))
        handoff_reason = _safe_get(res_dict, "handoff_reason", "reason", default=None)
        reply_text = _safe_get(res_dict, "reply_text", "text", "reply", default="") or ""

        # Optional diagnostics if your use case returns them
        intent = _safe_get(res_dict, "intent", "classified_intent", default=None)
        language = _safe_get(res_dict, "language", "lang", default=None)
        greeting_applied = _safe_get(res_dict, "greeting_applied", default=None)

        print("\n--- Decision ---")
        if intent is not None:
            print(f"intent: {intent}")
        if language is not None:
            print(f"language: {language}")
        if greeting_applied is not None:
            print(f"greeting_applied: {greeting_applied}")
        print(f"handoff: {should_handoff}")
        if should_handoff and handoff_reason:
            print(f"handoff_reason: {handoff_reason}")

        print("\n--- Reply ---")
        if should_handoff:
            print("(no response sent — silent handoff)")
        else:
            print(reply_text.strip() or "(empty reply_text)")

        print("-" * 60)


if __name__ == "__main__":
    main()
