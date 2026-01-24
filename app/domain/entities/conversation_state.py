from dataclasses import dataclass

from app.domain.entities.booking_state import BookingState
from app.domain.entities.selection_state import SelectionState


@dataclass(frozen=True)
class ConversationState:
    last_intent: str | None = None
    awaiting_booking: bool = False  # deprecated, use booking_state.status
    last_service: str | None = None
    booking_state: BookingState = BookingState()
    # New fields for durable persistence
    language: str | None = None  # "en" | "es" | None
    last_seen_at: float | None = None
    last_outbound_at: float | None = None
    greeted_at: float | None = None  # per-day greeting control
    selection_state: SelectionState = SelectionState()
