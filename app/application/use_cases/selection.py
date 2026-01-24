from __future__ import annotations

import logging
from dataclasses import dataclass

from app.application.ports.knowledge_base import KnowledgeBasePort
from app.domain.entities.selection_state import SelectionState


@dataclass(frozen=True)
class SelectionResult:
    """Result of selection processing."""

    updated_state: SelectionState
    service_key: str | None  # Resolved service key if found
    category: str | None  # Detected category if applicable
    needs_clarification: bool  # Whether user needs to choose between options


class SelectionUseCase:
    """Handle service category questions and service selection flow."""

    def __init__(self, kb: KnowledgeBasePort) -> None:
        self._kb = kb
        self._logger = logging.getLogger(__name__)

    def process_selection_intent(
        self,
        message_text: str,
        current_state: SelectionState,
        language: str,
    ) -> SelectionResult:
        """
        Process selection intent from user message.
        Returns updated SelectionState and resolved service if found.
        """
        normalized = message_text.lower().strip()

        # If already selected, return current state
        if current_state.status == "service_selected" and current_state.selected_service_key:
            return SelectionResult(
                updated_state=current_state,
                service_key=current_state.selected_service_key,
                category=None,
                needs_clarification=False,
            )

        # Try to resolve service from message
        resolved_service = self._kb.resolve_service_to_registry_key(message_text)

        if resolved_service:
            # Service found - mark as selected
            return SelectionResult(
                updated_state=SelectionState(
                    status="service_selected",
                    pending_category=None,
                    selected_service_key=resolved_service,
                    last_service_mention=message_text,
                    updated_at=None,  # Will be set by caller
                ),
                service_key=resolved_service,
                category=None,
                needs_clarification=False,
            )

        # Check for category questions
        category = self._detect_category(normalized)
        if category:
            # Check if category is ambiguous (multiple services in category)
            ambiguous = self._kb.is_ambiguous_category_question(message_text)
            if ambiguous:
                # Set pending category and ask for clarification
                return SelectionResult(
                    updated_state=SelectionState(
                        status="awaiting_service_choice",
                        pending_category=category,
                        selected_service_key=None,
                        last_service_mention=message_text,
                        updated_at=None,
                    ),
                    service_key=None,
                    category=category,
                    needs_clarification=True,
                )
            else:
                # Category is clear - try to resolve to a single service
                # For now, return category and let caller handle
                return SelectionResult(
                    updated_state=SelectionState(
                        status="awaiting_service_choice",
                        pending_category=category,
                        selected_service_key=None,
                        last_service_mention=message_text,
                        updated_at=None,
                    ),
                    service_key=None,
                    category=category,
                    needs_clarification=False,
                )

        # No service or category found - keep current state
        return SelectionResult(
            updated_state=current_state,
            service_key=None,
            category=None,
            needs_clarification=False,
        )

    def _detect_category(self, normalized_text: str) -> str | None:
        """Detect service category from text."""
        categories = {
            "laser": ("laser", "hair removal", "depilacion", "depilación"),
            "brows": ("brow", "eyebrow", "ceja", "cejas"),
            "lashes": ("lash", "eyelash", "pestaña", "pestañas"),
            "facial": ("facial", "skin", "piel", "exfoliate", "exfoliation", "deep clean", "blackhead"),
            "pmu": ("permanent makeup", "pmu", "tattoo", "tatuaje", "microblading"),
        }

        for category, keywords in categories.items():
            if any(keyword in normalized_text for keyword in keywords):
                return category

        return None

