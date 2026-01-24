from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.application.ports.calendar import CalendarPort
from app.application.ports.conversation_store import ConversationStorePort
from app.application.ports.service_catalog import ServiceCatalogPort
from app.application.utils.date_parser import (
    map_vague_time_to_range,
    parse_date_preference,
    parse_time_preference,
)
from app.domain.entities.booking_state import BookingState
from app.domain.entities.conversation_state import ConversationState


@dataclass(frozen=True)
class BookingResult:
    action: str
    message: str | None
    proposed_slots: list[datetime] | None
    updated_state: BookingState


class BookingUseCase:
    def __init__(
        self,
        calendar: CalendarPort,
        catalog: ServiceCatalogPort,
        store: ConversationStorePort,
        timezone: ZoneInfo,
        buffer_minutes: int = 15,
    ) -> None:
        self._calendar = calendar
        self._catalog = catalog
        self._store = store
        self._timezone = timezone
        self._buffer_minutes = buffer_minutes
        self._logger = logging.getLogger(__name__)

    def process_booking_intent(
        self,
        message_text: str,
        current_state: BookingState,
        service: str | None,
        language: str,
        conversation_state: "ConversationState | None" = None,
    ) -> BookingResult:
        """
        Process booking intent with service resolution from state.
        Uses current_state.service_key if present, falls back to conversation_state.
        """
        normalized_text = message_text.lower().strip()

        # Resolve service from state if not provided
        resolved_service = (
            service
            or current_state.service_key
            or (conversation_state.last_service if conversation_state else None)
            or (conversation_state.selection_state.selected_service_key if conversation_state else None)
        )

        if current_state.status == "none":
            if not resolved_service:
                # Need to collect service first
                return BookingResult(
                    action="ask_service",
                    message=None,
                    proposed_slots=None,
                    updated_state=BookingState(status="collecting_service"),
                )
            return self._start_booking_flow(resolved_service, language)

        if current_state.status == "collecting_service":
            # User provided service - try to resolve it
            if not resolved_service:
                # Still no service - keep asking
                return BookingResult(
                    action="ask_service",
                    message=None,
                    proposed_slots=None,
                    updated_state=current_state,
                )
            # Service found - move to collecting date
            return self._start_booking_flow(resolved_service, language)

        if current_state.status == "collecting_date":
            return self._process_date_input(message_text, current_state, resolved_service, language)

        if current_state.status == "collecting_time":
            return self._process_time_input(message_text, current_state, resolved_service, language)

        if current_state.status == "confirming":
            if self._is_confirmation(normalized_text):
                return self._confirm_booking(current_state, resolved_service, language)
            return BookingResult(
                action="confirm",
                message=None,
                proposed_slots=[current_state.proposed_time] if current_state.proposed_time else None,
                updated_state=current_state,
            )

        return BookingResult(
            action="reset",
            message=None,
            proposed_slots=None,
            updated_state=BookingState(),
        )

    def _start_booking_flow(self, service: str | None, language: str) -> BookingResult:
        return BookingResult(
            action="ask_date",
            message=None,
            proposed_slots=None,
            updated_state=BookingState(status="collecting_date", service_key=service),
        )

    def _process_date_input(
        self,
        message_text: str,
        current_state: BookingState,
        service: str | None,
        language: str,
    ) -> BookingResult:
        parsed_date = parse_date_preference(message_text, self._timezone)
        if not parsed_date:
            return BookingResult(
                action="ask_date",
                message=None,
                proposed_slots=None,
                updated_state=current_state,
            )

        duration = self._get_service_duration(service)
        slots = self._calendar.find_available_slots(parsed_date, duration)

        if not slots:
            return BookingResult(
                action="ask_date",
                message=None,
                proposed_slots=None,
                updated_state=current_state,
            )

        if len(slots) >= 2:
            return BookingResult(
                action="suggest_slots",
                message=None,
                proposed_slots=slots[:2],
                updated_state=BookingState(
                    status="collecting_time",
                    proposed_date=datetime.combine(parsed_date, datetime.min.time(), tzinfo=self._timezone),
                    service_key=service,
                ),
            )

        slot = slots[0]
        return BookingResult(
            action="suggest_slots",
            message=None,
            proposed_slots=[slot],
            updated_state=BookingState(
                status="collecting_time",
                proposed_date=datetime.combine(parsed_date, datetime.min.time(), tzinfo=self._timezone),
                service=service,
            ),
        )

    def _process_time_input(
        self,
        message_text: str,
        current_state: BookingState,
        service: str | None,
        language: str,
    ) -> BookingResult:
        if not current_state.proposed_date:
            return self._start_booking_flow(service, language)

        parsed_time = parse_time_preference(message_text)
        vague_range = map_vague_time_to_range(message_text)

        if parsed_time:
            hour, minute = parsed_time
            proposed_datetime = current_state.proposed_date.replace(hour=hour, minute=minute)
            duration = self._get_service_duration(service)
            end_datetime = proposed_datetime + timedelta(minutes=duration + self._buffer_minutes)

            if self._calendar.check_availability(proposed_datetime, end_datetime):
                return BookingResult(
                    action="confirm",
                    message=None,
                    proposed_slots=[proposed_datetime],
                    updated_state=BookingState(
                        status="confirming",
                        proposed_date=current_state.proposed_date,
                        proposed_time=proposed_datetime,
                        service_key=service,
                    ),
                )

            slots = self._calendar.find_available_slots(
                current_state.proposed_date.date(),
                duration,
                hour - 1,
                hour + 2,
            )
            if slots:
                return BookingResult(
                    action="suggest_slots",
                    message=None,
                    proposed_slots=slots[:2],
                    updated_state=current_state,
                )

        if vague_range:
            start_hour, end_hour = vague_range
            duration = self._get_service_duration(service)
            slots = self._calendar.find_available_slots(
                current_state.proposed_date.date(),
                duration,
                start_hour,
                end_hour,
            )
            if slots:
                return BookingResult(
                    action="suggest_slots",
                    message=None,
                    proposed_slots=slots[:2],
                    updated_state=current_state,
                )

        return BookingResult(
            action="ask_time",
            message=None,
            proposed_slots=None,
            updated_state=current_state,
        )

    def _confirm_booking(
        self,
        current_state: BookingState,
        service: str | None,
        language: str,
    ) -> BookingResult:
        if not current_state.proposed_time:
            return BookingResult(
                action="reset",
                message=None,
                proposed_slots=None,
                updated_state=BookingState(),
            )

        duration = self._get_service_duration(service)
        end_time = current_state.proposed_time + timedelta(minutes=duration + self._buffer_minutes)

        service_name = service or "appointment"
        if service:
            catalog_entry = self._catalog.get_service(service)
            if catalog_entry:
                service_name = catalog_entry.display_name

        try:
            event_id = self._calendar.create_event(
                start=current_state.proposed_time,
                end=end_time,
                title=f"{service_name} Appointment",
                description=f"Service: {service_name}",
            )

            return BookingResult(
                action="booked",
                message=None,
                proposed_slots=None,
                updated_state=BookingState(
                    status="confirmed",
                    proposed_date=current_state.proposed_date,
                    proposed_time=current_state.proposed_time,
                    service_key=service,
                    calendar_event_id=event_id,
                    event_id=event_id,
                ),
            )
        except Exception as e:
            self._logger.error("Error creating booking", extra={"error": str(e)})
            # Silent fallback: don't expose system errors
            return BookingResult(
                action="unavailable",
                message=None,
                proposed_slots=None,
                updated_state=current_state,
            )

    def _build_confirmation_prompt(self, state: BookingState, language: str) -> str:
        if not state.proposed_time:
            return ""

        service_name = state.service_key or "appointment"
        if state.service_key:
            catalog_entry = self._catalog.get_service(state.service_key)
            if catalog_entry:
                service_name = catalog_entry.display_name

        date_str = state.proposed_time.strftime("%B %d")
        time_str = state.proposed_time.strftime("%I:%M %p")

        if language == "es":
            return f"¿Te gustaría que reserve {service_name} el {date_str} a las {time_str}?"
        return f"Would you like me to book {service_name} on {date_str} at {time_str}?"

    def _is_confirmation(self, text: str) -> bool:
        confirmations = (
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
            "confirm",
            "book it",
            "si",
            "sí",
            "claro",
            "vale",
            "confirmar",
        )
        return any(conf in text for conf in confirmations)

    def _get_service_duration(self, service: str | None) -> int:
        if not service:
            return 60
        return self._catalog.get_duration_minutes(service)

