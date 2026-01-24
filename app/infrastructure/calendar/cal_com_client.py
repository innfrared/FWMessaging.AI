from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import httpx

from app.application.ports.calendar import CalendarPort
from app.core.config import settings


class CalComCalendar(CalendarPort):
    def __init__(
        self,
        api_key: str | None = None,
        calendar_id: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.CAL_COM_API_KEY
        self._calendar_id = calendar_id or settings.CAL_COM_CALENDAR_ID
        self._base_url = base_url or settings.CAL_COM_BASE_URL
        self._client = httpx.Client(timeout=10.0)
        self._logger = logging.getLogger(__name__)

        if not self._api_key:
            raise ValueError("CAL_COM_API_KEY is required for Cal.com calendar")

    def check_availability(self, start: datetime, end: datetime) -> bool:
        try:
            slots = self.find_available_slots(start.date(), int((end - start).total_seconds() / 60))
            for slot in slots:
                if slot <= start < slot + timedelta(minutes=int((end - start).total_seconds() / 60)):
                    return True
            return False
        except Exception as e:
            self._logger.error("Error checking availability", extra={"error": str(e)})
            return False

    def find_available_slots(
        self,
        date: date,
        duration_minutes: int,
        start_hour: int = 9,
        end_hour: int = 17,
    ) -> list[datetime]:
        try:
            start_datetime = datetime.combine(date, datetime.min.time().replace(hour=start_hour))
            end_datetime = datetime.combine(date, datetime.min.time().replace(hour=end_hour))

            url = f"{self._base_url}/slots"
            params = {
                "calendarId": self._calendar_id,
                "startTime": start_datetime.isoformat(),
                "endTime": end_datetime.isoformat(),
                "duration": duration_minutes,
            }
            headers = {"Authorization": f"Bearer {self._api_key}"}

            response = self._client.get(url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()
            slots: list[datetime] = []
            for slot_str in data.get("slots", []):
                try:
                    slot = datetime.fromisoformat(slot_str.replace("Z", "+00:00"))
                    slots.append(slot)
                except (ValueError, AttributeError):
                    continue

            return slots[:10]
        except Exception as e:
            self._logger.error("Error finding available slots", extra={"error": str(e)})
            return []

    def create_event(
        self,
        start: datetime,
        end: datetime,
        title: str,
        description: str | None = None,
        attendee_email: str | None = None,
    ) -> str:
        try:
            url = f"{self._base_url}/bookings"
            headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
            payload = {
                "eventTypeId": self._calendar_id,
                "startTime": start.isoformat(),
                "endTime": end.isoformat(),
                "title": title,
                "description": description or "",
            }
            if attendee_email:
                payload["attendeeEmail"] = attendee_email

            response = self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            event_id = data.get("id") or data.get("bookingId")
            if not event_id:
                raise ValueError("No event ID returned from Cal.com API")

            self._logger.info("Calendar event created", extra={"event_id": event_id, "title": title})
            return str(event_id)
        except Exception as e:
            self._logger.error("Error creating calendar event", extra={"error": str(e)})
            raise

    def cancel_event(self, event_id: str) -> bool:
        try:
            url = f"{self._base_url}/bookings/{event_id}"
            headers = {"Authorization": f"Bearer {self._api_key}"}

            response = self._client.delete(url, headers=headers)
            response.raise_for_status()

            self._logger.info("Calendar event cancelled", extra={"event_id": event_id})
            return True
        except Exception as e:
            self._logger.error("Error cancelling calendar event", extra={"error": str(e)})
            return False

