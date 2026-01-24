from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from app.application.ports.calendar import CalendarPort


class MockCalendar(CalendarPort):
    def __init__(self) -> None:
        self._events: dict[str, tuple[datetime, datetime]] = {}
        self._logger = logging.getLogger(__name__)

    def check_availability(self, start: datetime, end: datetime) -> bool:
        for event_start, event_end in self._events.values():
            if not (end <= event_start or start >= event_end):
                return False
        return True

    def find_available_slots(
        self,
        date: date,
        duration_minutes: int,
        start_hour: int = 9,
        end_hour: int = 17,
    ) -> list[datetime]:
        slots: list[datetime] = []
        current = datetime.combine(date, datetime.min.time().replace(hour=start_hour))
        end_time = datetime.combine(date, datetime.min.time().replace(hour=end_hour))

        while current + timedelta(minutes=duration_minutes) <= end_time:
            slot_end = current + timedelta(minutes=duration_minutes)
            if self.check_availability(current, slot_end):
                slots.append(current)
            current += timedelta(minutes=30)

        return slots[:10]

    def create_event(
        self,
        start: datetime,
        end: datetime,
        title: str,
        description: str | None = None,
        attendee_email: str | None = None,
    ) -> str:
        event_id = f"mock_event_{len(self._events) + 1}"
        self._events[event_id] = (start, end)
        self._logger.info(
            "Mock calendar event created",
            extra={
                "event_id": event_id,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "title": title,
            },
        )
        return event_id

    def cancel_event(self, event_id: str) -> bool:
        if event_id in self._events:
            del self._events[event_id]
            self._logger.info("Mock calendar event cancelled", extra={"event_id": event_id})
            return True
        return False

