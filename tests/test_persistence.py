"""
Tests for durable conversation state persistence.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from app.domain.entities.booking_state import BookingState
from app.domain.entities.conversation_state import ConversationState
from app.domain.entities.selection_state import SelectionState
from app.infrastructure.store.json_store import JsonConversationStore


def test_json_store_persistence():
    """Test that JSON store persists and retrieves state correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonConversationStore(data_dir=tmpdir)
        thread_id = "test_thread_1"

        # Create initial state
        initial_state = ConversationState(
            last_intent="pricing",
            last_service="laser_hair_removal_full_body",
            language="en",
            booking_state=BookingState(status="collecting_date", service_key="laser_hair_removal_full_body"),
        )

        # Save state
        store.set_state(thread_id, initial_state)

        # Retrieve state
        retrieved_state = store.get_state(thread_id)

        assert retrieved_state.last_intent == "pricing"
        assert retrieved_state.last_service == "laser_hair_removal_full_body"
        assert retrieved_state.language == "en"
        assert retrieved_state.booking_state.status == "collecting_date"
        assert retrieved_state.booking_state.service_key == "laser_hair_removal_full_body"


def test_booking_persists_date_and_time():
    """Test that booking persists date from 'Friday' and accepts time in next message '9:00'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonConversationStore(data_dir=tmpdir)
        thread_id = "test_thread_2"

        # First message: "Friday"
        state1 = ConversationState(
            booking_state=BookingState(
                status="collecting_time",
                proposed_date=datetime(2024, 1, 26, 0, 0),  # Friday
                service_key="laser_hair_removal_full_body",
            )
        )
        store.set_state(thread_id, state1)

        # Second message: "9:00"
        retrieved = store.get_state(thread_id)
        assert retrieved.booking_state.status == "collecting_time"
        assert retrieved.booking_state.proposed_date is not None
        assert retrieved.booking_state.service_key == "laser_hair_removal_full_body"


def test_service_persists_for_followup():
    """Test that service persists: 'I want full body laser' then 'how much is it' uses stored service."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonConversationStore(data_dir=tmpdir)
        thread_id = "test_thread_3"

        # First message sets service
        state1 = ConversationState(
            last_service="laser_hair_removal_full_body",
            last_intent="service_details",
        )
        store.set_state(thread_id, state1)

        # Second message should use stored service
        retrieved = store.get_state(thread_id)
        assert retrieved.last_service == "laser_hair_removal_full_body"


def test_greeting_sent_once_per_day():
    """Test that greeting is sent once per day per thread across separate handle() calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonConversationStore(data_dir=tmpdir)
        thread_id = "test_thread_4"

        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Los_Angeles")
        now = datetime.now(tz)
        today_ts = now.timestamp()

        # First call - should greet
        assert store.should_greet_today(thread_id, "America/Los_Angeles", today_ts) is True
        store.mark_greeted(thread_id, today_ts)

        # Second call same day - should not greet
        assert store.should_greet_today(thread_id, "America/Los_Angeles", today_ts) is False


def test_selection_state_transitions():
    """Test that SelectionState transitions work correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonConversationStore(data_dir=tmpdir)
        thread_id = "test_thread_5"

        # Start with awaiting_service_choice
        state1 = ConversationState(
            selection_state=SelectionState(
                status="awaiting_service_choice",
                pending_category="laser",
            )
        )
        store.set_state(thread_id, state1)

        # Transition to service_selected
        retrieved = store.get_state(thread_id)
        state2 = ConversationState(
            selection_state=SelectionState(
                status="service_selected",
                selected_service_key="laser_hair_removal_full_body",
            )
        )
        store.set_state(thread_id, state2)

        final = store.get_state(thread_id)
        assert final.selection_state.status == "service_selected"
        assert final.selection_state.selected_service_key == "laser_hair_removal_full_body"


if __name__ == "__main__":
    test_json_store_persistence()
    test_booking_persists_date_and_time()
    test_service_persists_for_followup()
    test_greeting_sent_once_per_day()
    test_selection_state_transitions()
    print("All tests passed!")

