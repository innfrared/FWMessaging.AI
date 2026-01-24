from __future__ import annotations

from app.domain.entities.booking_state import BookingState
from app.domain.entities.conversation_state import ConversationState
from app.domain.entities.selection_state import SelectionState


def reset_booking_state(state: ConversationState) -> ConversationState:
    """Reset booking state to initial state."""
    return ConversationState(
        last_intent=state.last_intent,
        awaiting_booking=False,
        last_service=state.last_service,
        booking_state=BookingState(),
        language=state.language,
        last_seen_at=state.last_seen_at,
        last_outbound_at=state.last_outbound_at,
        greeted_at=state.greeted_at,
        selection_state=state.selection_state,
    )


def reset_selection_state(state: ConversationState) -> ConversationState:
    """Reset selection state to initial state."""
    return ConversationState(
        last_intent=state.last_intent,
        awaiting_booking=state.awaiting_booking,
        last_service=state.last_service,
        booking_state=state.booking_state,
        language=state.language,
        last_seen_at=state.last_seen_at,
        last_outbound_at=state.last_outbound_at,
        greeted_at=state.greeted_at,
        selection_state=SelectionState(),
    )


def reset_all_transient(state: ConversationState) -> ConversationState:
    """Reset all transient state (booking and selection) to initial state."""
    return ConversationState(
        last_intent=state.last_intent,
        awaiting_booking=False,
        last_service=state.last_service,
        booking_state=BookingState(),
        language=state.language,
        last_seen_at=state.last_seen_at,
        last_outbound_at=state.last_outbound_at,
        greeted_at=state.greeted_at,
        selection_state=SelectionState(),
    )

