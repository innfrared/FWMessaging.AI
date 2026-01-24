from abc import ABC, abstractmethod
from typing import Any

from app.domain.entities.conversation_state import ConversationState


class ConversationStorePort(ABC):
    @abstractmethod
    def get_history(self, thread_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def append_message(self, thread_id: str, role: str, text: str, meta: dict[str, Any] | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def has_processed(self, message_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mark_processed(self, message_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_state(self, thread_id: str) -> ConversationState:
        raise NotImplementedError

    @abstractmethod
    def set_state(self, thread_id: str, state: ConversationState) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_first_outbound_message_today(self, thread_id: str, timezone: str, now_ts: float | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mark_outbound(self, thread_id: str, timestamp: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def should_greet_today(self, thread_id: str, timezone: str, now_ts: float | None = None) -> bool:
        """
        Check if greeting should be sent today for this thread.
        This is atomic: returns True only if no greeting was sent today.
        """
        raise NotImplementedError

    @abstractmethod
    def mark_greeted(self, thread_id: str, timestamp: float) -> None:
        """
        Mark that a greeting was sent for this thread at the given timestamp.
        """
        raise NotImplementedError

    @abstractmethod
    def should_process_message(self, thread_id: str, message_id: str, cooldown_seconds: float = 3.0, now_ts: float | None = None) -> tuple[bool, str | None]:
        """
        Check if message should be processed (debounce logic).
        Returns (should_process, previous_message_id_if_coalesced).
        If within cooldown, returns (False, previous_message_id) to indicate coalescing.
        """
        raise NotImplementedError

    @abstractmethod
    def mark_message_received(self, thread_id: str, message_id: str, timestamp: float) -> None:
        """
        Mark that a message was received for this thread.
        """
        raise NotImplementedError

    @abstractmethod
    def get_recent_messages(self, thread_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recent messages for context.
        Returns the last N messages from the thread history.
        """
        raise NotImplementedError
