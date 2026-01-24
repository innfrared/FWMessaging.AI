from __future__ import annotations

from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo

from app.application.ports.conversation_store import ConversationStorePort
from app.domain.entities.conversation_state import ConversationState


class MemoryConversationStore(ConversationStorePort):
    def __init__(self, history_limit: int = 30) -> None:
        self._threads: dict[str, list[dict[str, Any]]] = {}
        self._processed: set[str] = set()
        self._states: dict[str, ConversationState] = {}
        self._last_outbound_ts: dict[str, float] = {}
        self._last_greeted_at: dict[str, float] = {}
        self._last_received_message_at: dict[str, float] = {}
        self._pending_message_id: dict[str, str] = {}
        self._history_limit = history_limit

    def get_history(self, thread_id: str) -> list[dict[str, Any]]:
        return list(self._threads.get(thread_id, []))

    def append_message(self, thread_id: str, role: str, text: str, meta: dict[str, Any] | None = None) -> None:
        self._threads.setdefault(thread_id, [])
        self._threads[thread_id].append(
            {
                "role": role,
                "content": text,
                "meta": dict(meta or {}),
            }
        )
        if len(self._threads[thread_id]) > self._history_limit:
            self._threads[thread_id] = self._threads[thread_id][-self._history_limit :]

    def has_processed(self, message_id: str) -> bool:
        return message_id in self._processed

    def mark_processed(self, message_id: str) -> None:
        self._processed.add(message_id)

    def get_state(self, thread_id: str) -> ConversationState:
        return self._states.get(thread_id, ConversationState())

    def set_state(self, thread_id: str, state: ConversationState) -> None:
        self._states[thread_id] = state

    def is_first_outbound_message_today(self, thread_id: str, timezone: str, now_ts: float | None = None) -> bool:
        last_ts = self._last_outbound_ts.get(thread_id)
        tz = _safe_timezone(timezone)
        now = datetime.fromtimestamp(now_ts, tz) if now_ts is not None else datetime.now(tz)
        if last_ts is None:
            return True
        last_dt = datetime.fromtimestamp(last_ts, tz)
        return last_dt.date() != now.date()

    def mark_outbound(self, thread_id: str, timestamp: float) -> None:
        self._last_outbound_ts[thread_id] = timestamp

    def should_greet_today(self, thread_id: str, timezone: str, now_ts: float | None = None) -> bool:
        """
        Atomic check: returns True only if no greeting was sent today for this thread.
        This prevents duplicate greetings when messages arrive close together.
        """
        last_greeted_ts = self._last_greeted_at.get(thread_id)
        tz = _safe_timezone(timezone)
        now = datetime.fromtimestamp(now_ts, tz) if now_ts is not None else datetime.now(tz)
        if last_greeted_ts is None:
            return True
        last_greeted_dt = datetime.fromtimestamp(last_greeted_ts, tz)
        return last_greeted_dt.date() != now.date()

    def mark_greeted(self, thread_id: str, timestamp: float) -> None:
        """Mark that a greeting was sent for this thread."""
        self._last_greeted_at[thread_id] = timestamp

    def should_process_message(self, thread_id: str, message_id: str, cooldown_seconds: float = 3.0, now_ts: float | None = None) -> tuple[bool, str | None]:
        """
        Check if message should be processed (debounce logic).
        Returns (should_process, previous_message_id_if_coalesced).
        If within cooldown, returns (False, previous_message_id) to indicate coalescing.
        """
        if now_ts is None:
            now_ts = datetime.now().timestamp()
        
        last_received_ts = self._last_received_message_at.get(thread_id)
        pending_id = self._pending_message_id.get(thread_id)
        
        if last_received_ts is None:
            # First message for this thread
            return (True, None)
        
        time_since_last = now_ts - last_received_ts
        if time_since_last < cooldown_seconds:
            # Within cooldown - coalesce with previous message
            return (False, pending_id)
        
        # Outside cooldown - process this message
        return (True, None)

    def mark_message_received(self, thread_id: str, message_id: str, timestamp: float) -> None:
        """Mark that a message was received for this thread."""
        self._last_received_message_at[thread_id] = timestamp
        self._pending_message_id[thread_id] = message_id

    def get_recent_messages(self, thread_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent messages for context."""
        messages = self.get_history(thread_id)
        return messages[-limit:] if messages else []


def _safe_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")
