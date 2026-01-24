from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")

from app.application.use_cases.booking import BookingResult, BookingUseCase
from app.application.utils.date_parser import map_vague_time_to_range, parse_date_preference, parse_time_preference
from app.domain.entities.booking_state import BookingState
from app.infrastructure.calendar.mock_calendar import MockCalendar
from app.infrastructure.knowledge.service_catalog_store import ServiceCatalogStore
from app.infrastructure.store.memory_store import MemoryConversationStore


def test_date_parsing():
    tz = ZoneInfo("America/Los_Angeles")
    today = date.today()

    result = parse_date_preference("tomorrow", tz, today)
    assert result == today + timedelta(days=1), f"Expected {today + timedelta(days=1)}, got {result}"
    assert parse_date_preference("next Wednesday", tz, today) is not None
    assert parse_date_preference("March 15", tz, today) is not None
    print("✅ Date parsing tests passed")


def test_time_parsing():
    assert parse_time_preference("2pm") == (14, 0)
    assert parse_time_preference("14:00") == (14, 0)
    assert parse_time_preference("9:30 am") == (9, 30)
    print("✅ Time parsing tests passed")


def test_vague_time_mapping():
    assert map_vague_time_to_range("morning") == (9, 12)
    assert map_vague_time_to_range("afternoon") == (12, 17)
    assert map_vague_time_to_range("evening") == (17, 20)
    print("✅ Vague time mapping tests passed")


def test_booking_flow():
    calendar = MockCalendar()
    catalog = ServiceCatalogStore()
    store = MemoryConversationStore()
    tz = ZoneInfo("America/Los_Angeles")

    use_case = BookingUseCase(calendar=calendar, catalog=catalog, store=store, timezone=tz)

    state = BookingState()
    result = use_case.process_booking_intent("I want to book", state, "full body diode laser", "en")
    assert result.action == "ask_date"
    assert result.message is not None
    print("✅ Booking flow start test passed")

    state = BookingState(status="collecting_date", service="full body diode laser")
    result = use_case.process_booking_intent("tomorrow", state, "full body diode laser", "en")
    assert result.action in ("suggest_slots", "ask_date")
    print("✅ Booking date input test passed")


def test_service_catalog():
    catalog = ServiceCatalogStore()

    entry = catalog.get_service("full body diode laser")
    assert entry is not None
    assert entry.price_min == 150
    assert entry.duration_minutes_min == 60

    duration = catalog.get_duration_minutes("full body diode laser")
    assert duration == 60

    price_range = catalog.get_price_range("facial deep blackhead removal")
    assert price_range == (120, 150)
    print("✅ Service catalog tests passed")


if __name__ == "__main__":
    test_date_parsing()
    test_time_parsing()
    test_vague_time_mapping()
    test_booking_flow()
    test_service_catalog()
    print("\n✅ All tests passed!")

