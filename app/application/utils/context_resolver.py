from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.ports.knowledge_base import KnowledgeBasePort
from app.application.utils.message_rules import (
    asks_about_duration,
    asks_about_sessions,
    contains_date_or_time,
    has_equipment_intent,
    has_explicit_price_intent,
    is_booking_request,
    is_informational_question,
)
from app.domain.entities.conversation_state import ConversationState


@dataclass(frozen=True)
class ContextResolution:
    """Resolved context from user message and conversation state."""

    resolved_language: str  # "en" or "es"
    resolved_service_key: str | None
    is_booking_request: bool
    is_duration_question: bool
    is_price_question: bool
    is_sessions_question: bool
    is_equipment_question: bool
    is_service_question: bool
    is_follow_up: bool


def resolve_context(
    thread_id: str,
    user_text: str,
    recent_messages: list[dict[str, Any]],
    state: ConversationState,
    kb: KnowledgeBasePort,
) -> ContextResolution:
    """
    Resolve context from user message, recent messages, and conversation state.
    Centralizes context detection logic.
    """
    # Resolve language
    resolved_language = state.language or "en"  # Default to English if not set

    # Detect language from message if not set
    if not state.language:
        normalized = user_text.lower()
        spanish_indicators = ("hola", "gracias", "precio", "cuanto", "cuánto", "disponibilidad", "servicio")
        if any(indicator in normalized for indicator in spanish_indicators):
            resolved_language = "es"
        else:
            resolved_language = "en"

    # Resolve service key
    resolved_service_key = None

    # First, try to resolve from user text
    service_from_text = kb.resolve_service_to_registry_key(user_text)
    if service_from_text:
        resolved_service_key = service_from_text
    else:
        # Fallback to state
        resolved_service_key = (
            state.last_service
            or state.booking_state.service_key
            or state.selection_state.selected_service_key
        )

    # Detect question types
    is_booking = is_booking_request(user_text)
    is_duration = asks_about_duration(user_text)
    is_price = has_explicit_price_intent(user_text)
    is_sessions = asks_about_sessions(user_text)
    is_equipment = has_equipment_intent(user_text)
    is_service = bool(service_from_text) or bool(resolved_service_key)

    # Detect follow-up
    is_follow_up = _detect_follow_up(user_text, recent_messages, state)

    return ContextResolution(
        resolved_language=resolved_language,
        resolved_service_key=resolved_service_key,
        is_booking_request=is_booking,
        is_duration_question=is_duration,
        is_price_question=is_price,
        is_sessions_question=is_sessions,
        is_equipment_question=is_equipment,
        is_service_question=is_service,
        is_follow_up=is_follow_up,
    )


def _detect_follow_up(
    user_text: str,
    recent_messages: list[dict[str, Any]],
    state: ConversationState,
) -> bool:
    """Detect if this is a follow-up message."""
    normalized = user_text.lower().strip()

    # Common follow-up patterns
    follow_up_patterns = (
        "how much",
        "how long",
        "how many",
        "what about",
        "what is",
        "what's",
        "tell me",
        "cuanto",
        "cuánto",
        "cuanto tiempo",
        "cuantas",
        "cuántas",
        "que es",
        "qué es",
    )

    # Check if message contains follow-up patterns
    if any(pattern in normalized for pattern in follow_up_patterns):
        return True

    # Check if there's recent conversation context
    if recent_messages:
        # If there's a recent assistant message, this might be a follow-up
        last_assistant_msg = next(
            (msg for msg in reversed(recent_messages) if msg.get("role") == "assistant"),
            None,
        )
        if last_assistant_msg:
            # Check if user is asking about something mentioned in last message
            last_text = last_assistant_msg.get("text", "").lower()
            if any(
                word in normalized
                for word in ("it", "that", "this", "eso", "esto", "lo", "la")
            ):
                return True

    # Check if state indicates ongoing conversation
    if state.last_intent or state.last_service or state.booking_state.status != "none":
        # Short messages after a question are likely follow-ups
        if len(normalized.split()) <= 5:
            return True

    return False

