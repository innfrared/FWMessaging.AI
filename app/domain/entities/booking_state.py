from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BookingState:
    status: str = "none"  # "none", "collecting_service", "collecting_date", "collecting_time", "confirming", "confirmed"
    proposed_date: datetime | None = None
    proposed_time: datetime | None = None
    service_key: str | None = None  # renamed from service
    calendar_event_id: str | None = None
    # ISO string fields for JSON serialization (derived from datetime objects)
    proposed_date_iso: str | None = None  # YYYY-MM-DD
    proposed_time_24h: str | None = None  # HH:MM
    proposed_slot_start_iso: str | None = None  # full ISO datetime
    timezone: str | None = None
    duration_minutes: int | None = None
    event_id: str | None = None  # alias for calendar_event_id, prefer this
    updated_at: float | None = None

