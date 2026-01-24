from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime


class CalendarPort(ABC):
    @abstractmethod
    def check_availability(self, start: datetime, end: datetime) -> bool:
        """Check if time slot is available."""
        raise NotImplementedError

    @abstractmethod
    def find_available_slots(
        self,
        date: date,
        duration_minutes: int,
        start_hour: int = 9,
        end_hour: int = 17,
    ) -> list[datetime]:
        """Find available time slots for a given date and duration."""
        raise NotImplementedError

    @abstractmethod
    def create_event(
        self,
        start: datetime,
        end: datetime,
        title: str,
        description: str | None = None,
        attendee_email: str | None = None,
    ) -> str:
        """Create calendar event. Returns event_id."""
        raise NotImplementedError

    @abstractmethod
    def cancel_event(self, event_id: str) -> bool:
        """Cancel calendar event. Returns True if successful."""
        raise NotImplementedError

