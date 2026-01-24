from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from app.application.ports.conversation_store import ConversationStorePort
from app.domain.entities.booking_state import BookingState
from app.domain.entities.conversation_state import ConversationState
from app.domain.entities.selection_state import SelectionState


class JsonConversationStore(ConversationStorePort):
    def __init__(self, data_dir: str = "./data/threads", history_limit: int = 50) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._history_limit = history_limit
        self._locks: dict[str, threading.Lock] = {}
        self._lock_lock = threading.Lock()  # Lock for managing locks dict

    def _get_lock(self, thread_id: str) -> threading.Lock:
        """Get or create a lock for a thread_id."""
        with self._lock_lock:
            if thread_id not in self._locks:
                self._locks[thread_id] = threading.Lock()
            return self._locks[thread_id]

    def _get_file_path(self, thread_id: str) -> Path:
        """Get the file path for a thread_id."""
        return self._data_dir / f"{thread_id}.json"

    def _load_thread_data(self, thread_id: str) -> dict[str, Any]:
        """Load thread data from JSON file, return default if missing."""
        file_path = self._get_file_path(thread_id)
        if not file_path.exists():
            return {
                "thread_id": thread_id,
                "state": self._serialize_state(ConversationState()),
                "messages": [],
                "processed_message_ids": [],
                "debounce": {"last_message_id": None, "last_received_at": None},
                "version": 1,
            }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all required fields exist
                if "version" not in data:
                    data["version"] = 1
                if "debounce" not in data:
                    data["debounce"] = {"last_message_id": None, "last_received_at": None}
                return data
        except (json.JSONDecodeError, IOError) as e:
            # If file is corrupted, return defaults
            return {
                "thread_id": thread_id,
                "state": self._serialize_state(ConversationState()),
                "messages": [],
                "processed_message_ids": [],
                "debounce": {"last_message_id": None, "last_received_at": None},
                "version": 1,
            }

    def _save_thread_data(self, thread_id: str, data: dict[str, Any]) -> None:
        """Save thread data to JSON file atomically."""
        file_path = self._get_file_path(thread_id)
        temp_path = file_path.with_suffix(".json.tmp")

        try:
            # Write to temp file
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Atomic rename
            temp_path.replace(file_path)
        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise

    def _serialize_state(self, state: ConversationState) -> dict[str, Any]:
        """Serialize ConversationState to dict."""
        booking_dict = self._serialize_booking_state(state.booking_state)
        selection_dict = self._serialize_selection_state(state.selection_state)

        return {
            "last_intent": state.last_intent,
            "awaiting_booking": state.awaiting_booking,
            "last_service": state.last_service,
            "booking_state": booking_dict,
            "language": state.language,
            "last_seen_at": state.last_seen_at,
            "last_outbound_at": state.last_outbound_at,
            "greeted_at": state.greeted_at,
            "selection_state": selection_dict,
        }

    def _deserialize_state(self, data: dict[str, Any]) -> ConversationState:
        """Deserialize dict to ConversationState."""
        booking_state = self._deserialize_booking_state(data.get("booking_state", {}))
        selection_state = self._deserialize_selection_state(data.get("selection_state", {}))

        return ConversationState(
            last_intent=data.get("last_intent"),
            awaiting_booking=data.get("awaiting_booking", False),
            last_service=data.get("last_service"),
            booking_state=booking_state,
            language=data.get("language"),
            last_seen_at=data.get("last_seen_at"),
            last_outbound_at=data.get("last_outbound_at"),
            greeted_at=data.get("greeted_at"),
            selection_state=selection_state,
        )

    def _serialize_booking_state(self, state: BookingState) -> dict[str, Any]:
        """Serialize BookingState to dict with ISO string conversion."""
        result = {
            "status": state.status,
            "service_key": state.service_key,
            "calendar_event_id": state.calendar_event_id,
            "event_id": state.event_id,
            "timezone": state.timezone,
            "duration_minutes": state.duration_minutes,
            "updated_at": state.updated_at,
        }

        # Convert datetime to ISO strings
        if state.proposed_date:
            result["proposed_date_iso"] = state.proposed_date.strftime("%Y-%m-%d")
        else:
            result["proposed_date_iso"] = None

        if state.proposed_time:
            result["proposed_time_24h"] = state.proposed_time.strftime("%H:%M")
            result["proposed_slot_start_iso"] = state.proposed_time.isoformat()
        else:
            result["proposed_time_24h"] = None
            result["proposed_slot_start_iso"] = None

        # Store datetime objects as ISO strings for JSON
        if state.proposed_date:
            result["proposed_date"] = state.proposed_date.isoformat()
        else:
            result["proposed_date"] = None

        if state.proposed_time:
            result["proposed_time"] = state.proposed_time.isoformat()
        else:
            result["proposed_time"] = None

        return result

    def _deserialize_booking_state(self, data: dict[str, Any]) -> BookingState:
        """Deserialize dict to BookingState with datetime parsing."""
        # Parse datetime from ISO strings
        proposed_date = None
        if data.get("proposed_date"):
            try:
                proposed_date = datetime.fromisoformat(data["proposed_date"])
            except (ValueError, TypeError):
                pass

        proposed_time = None
        if data.get("proposed_time"):
            try:
                proposed_time = datetime.fromisoformat(data["proposed_time"])
            except (ValueError, TypeError):
                pass

        return BookingState(
            status=data.get("status", "none"),
            proposed_date=proposed_date,
            proposed_time=proposed_time,
            service_key=data.get("service_key"),
            calendar_event_id=data.get("calendar_event_id") or data.get("event_id"),
            event_id=data.get("event_id") or data.get("calendar_event_id"),
            proposed_date_iso=data.get("proposed_date_iso"),
            proposed_time_24h=data.get("proposed_time_24h"),
            proposed_slot_start_iso=data.get("proposed_slot_start_iso"),
            timezone=data.get("timezone"),
            duration_minutes=data.get("duration_minutes"),
            updated_at=data.get("updated_at"),
        )

    def _serialize_selection_state(self, state: SelectionState) -> dict[str, Any]:
        """Serialize SelectionState to dict."""
        return {
            "status": state.status,
            "pending_category": state.pending_category,
            "selected_service_key": state.selected_service_key,
            "last_service_mention": state.last_service_mention,
            "updated_at": state.updated_at,
        }

    def _deserialize_selection_state(self, data: dict[str, Any]) -> SelectionState:
        """Deserialize dict to SelectionState."""
        return SelectionState(
            status=data.get("status", "none"),
            pending_category=data.get("pending_category"),
            selected_service_key=data.get("selected_service_key"),
            last_service_mention=data.get("last_service_mention"),
            updated_at=data.get("updated_at"),
        )

    def get_history(self, thread_id: str) -> list[dict[str, Any]]:
        """Get message history for a thread."""
        with self._get_lock(thread_id):
            data = self._load_thread_data(thread_id)
            return data.get("messages", [])

    def get_recent_messages(self, thread_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent messages for context."""
        messages = self.get_history(thread_id)
        return messages[-limit:] if messages else []

    def append_message(self, thread_id: str, role: str, text: str, meta: dict[str, Any] | None = None) -> None:
        """Append a message to thread history."""
        with self._get_lock(thread_id):
            data = self._load_thread_data(thread_id)
            messages = data.get("messages", [])

            message_entry = {
                "role": role,
                "text": text,
                "ts": datetime.now().timestamp(),
                "meta": dict(meta or {}),
            }
            messages.append(message_entry)

            # Keep last N messages
            if len(messages) > self._history_limit:
                messages = messages[-self._history_limit :]

            data["messages"] = messages
            self._save_thread_data(thread_id, data)

    def has_processed(self, message_id: str) -> bool:
        """Check if message has been processed."""
        # Search all thread files - this is expensive but necessary for cross-thread deduplication
        # In production, consider indexing processed_message_ids separately
        for file_path in self._data_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if message_id in data.get("processed_message_ids", []):
                        return True
            except Exception:
                continue
        return False

    def mark_processed(self, message_id: str) -> None:
        """Mark a message as processed."""
        # This method is called without thread_id, so we can't update a specific thread
        # The mark_message_received method already tracks processed IDs per thread
        # This is a no-op for JSON store - tracking happens in mark_message_received
        pass

    def get_state(self, thread_id: str) -> ConversationState:
        """Get conversation state for a thread."""
        with self._get_lock(thread_id):
            data = self._load_thread_data(thread_id)
            return self._deserialize_state(data.get("state", {}))
    
    def _get_state_without_lock(self, thread_id: str) -> ConversationState:
        """Get conversation state for a thread without acquiring a lock.
        Use this when you're already inside a lock for this thread_id."""
        data = self._load_thread_data(thread_id)
        return self._deserialize_state(data.get("state", {}))

    def set_state(self, thread_id: str, state: ConversationState) -> None:
        """Set conversation state for a thread."""
        with self._get_lock(thread_id):
            data = self._load_thread_data(thread_id)
            data["state"] = self._serialize_state(state)
            self._save_thread_data(thread_id, data)
    
    def _set_state_without_lock(self, thread_id: str, state: ConversationState) -> None:
        """Set conversation state for a thread without acquiring a lock.
        Use this when you're already inside a lock for this thread_id."""
        data = self._load_thread_data(thread_id)
        data["state"] = self._serialize_state(state)
        self._save_thread_data(thread_id, data)

    def is_first_outbound_message_today(self, thread_id: str, timezone: str, now_ts: float | None = None) -> bool:
        """Check if this is the first outbound message today."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        if now_ts is None:
            now_ts = datetime.now().timestamp()

        tz = ZoneInfo(timezone)
        now = datetime.fromtimestamp(now_ts, tz=tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_ts = today_start.timestamp()

        state = self.get_state(thread_id)
        last_outbound = state.last_outbound_at

        if last_outbound is None:
            return True

        return last_outbound < today_start_ts

    def mark_outbound(self, thread_id: str, timestamp: float) -> None:
        """Mark that an outbound message was sent."""
        with self._get_lock(thread_id):
            state = self._get_state_without_lock(thread_id)
            state = ConversationState(
                last_intent=state.last_intent,
                awaiting_booking=state.awaiting_booking,
                last_service=state.last_service,
                booking_state=state.booking_state,
                language=state.language,
                last_seen_at=state.last_seen_at,
                last_outbound_at=timestamp,
                greeted_at=state.greeted_at,
                selection_state=state.selection_state,
            )
            self._set_state_without_lock(thread_id, state)

    def should_greet_today(self, thread_id: str, timezone: str, now_ts: float | None = None) -> bool:
        """Check if greeting should be sent today for this thread."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo

            logger.info(f"should_greet_today: Starting for thread_id={thread_id}")
            if now_ts is None:
                now_ts = datetime.now().timestamp()

            tz = ZoneInfo(timezone)
            now = datetime.fromtimestamp(now_ts, tz=tz)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_start_ts = today_start.timestamp()

            logger.info(f"should_greet_today: Getting state for thread_id={thread_id}")
            state = self.get_state(thread_id)
            logger.info(f"should_greet_today: Got state, greeted_at={state.greeted_at}")
            greeted_at = state.greeted_at

            if greeted_at is None:
                logger.info(f"should_greet_today: greeted_at is None, returning True")
                return True

            result = greeted_at < today_start_ts
            logger.info(f"should_greet_today: Comparing {greeted_at} < {today_start_ts} = {result}")
            return result
        except Exception as e:
            import traceback
            error_str = f"Error in should_greet_today for thread_id={thread_id}: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_str, exc_info=True)
            print(f"ERROR in should_greet_today: {error_str}")  # Fallback print
            # Default to True to allow greeting if there's an error
            return True

    def mark_greeted(self, thread_id: str, timestamp: float) -> None:
        """Mark that a greeting was sent for this thread."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"mark_greeted: Starting for thread_id={thread_id}, timestamp={timestamp}")
            logger.info(f"mark_greeted: Getting lock for thread_id={thread_id}")
            with self._get_lock(thread_id):
                logger.info(f"mark_greeted: Lock acquired, getting state")
                state = self._get_state_without_lock(thread_id)
                logger.info(f"mark_greeted: Got state, creating new state with greeted_at={timestamp}")
                state = ConversationState(
                    last_intent=state.last_intent,
                    awaiting_booking=state.awaiting_booking,
                    last_service=state.last_service,
                    booking_state=state.booking_state,
                    language=state.language,
                    last_seen_at=state.last_seen_at,
                    last_outbound_at=state.last_outbound_at,
                    greeted_at=timestamp,
                    selection_state=state.selection_state,
                )
                logger.info(f"mark_greeted: Setting state")
                self._set_state_without_lock(thread_id, state)
                logger.info(f"mark_greeted: State set successfully")
        except Exception as e:
            import traceback
            error_str = f"Error in mark_greeted for thread_id={thread_id}: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_str, exc_info=True)
            print(f"ERROR in mark_greeted: {error_str}")  # Fallback print
            raise

    def should_process_message(
        self, thread_id: str, message_id: str, cooldown_seconds: float = 3.0, now_ts: float | None = None
    ) -> tuple[bool, str | None]:
        """Check if message should be processed (debounce logic)."""
        from datetime import datetime

        if now_ts is None:
            now_ts = datetime.now().timestamp()

        with self._get_lock(thread_id):
            data = self._load_thread_data(thread_id)
            debounce = data.get("debounce", {})
            last_received_at = debounce.get("last_received_at")
            pending_id = debounce.get("last_message_id")

            if last_received_at is None:
                return (True, None)

            time_since_last = now_ts - last_received_at
            if time_since_last < cooldown_seconds:
                return (False, pending_id)

            return (True, None)

    def mark_message_received(self, thread_id: str, message_id: str, timestamp: float) -> None:
        """Mark that a message was received for this thread."""
        with self._get_lock(thread_id):
            data = self._load_thread_data(thread_id)
            data["debounce"] = {
                "last_message_id": message_id,
                "last_received_at": timestamp,
            }
            # Also track processed message IDs per thread
            processed = data.get("processed_message_ids", [])
            if message_id not in processed:
                processed.append(message_id)
                # Keep last 1000 processed IDs
                if len(processed) > 1000:
                    processed = processed[-1000:]
            data["processed_message_ids"] = processed
            self._save_thread_data(thread_id, data)

