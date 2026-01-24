from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

VAGUE_TIME_RANGES = {
    "morning": (9, 12),
    "afternoon": (12, 17),
    "evening": (17, 20),
    "night": (18, 21),
    "mañana": (9, 12),
    "tarde": (12, 17),
    "noche": (17, 20),
}


def parse_date_preference(text: str, timezone: ZoneInfo, reference_date: date | None = None) -> date | None:
    """Parse date preference from text. Returns date or None if not found."""
    if reference_date is None:
        reference_date = datetime.now(timezone).date()

    normalized = text.lower().strip()

    if "today" in normalized or "hoy" in normalized:
        return reference_date

    if "tomorrow" in normalized or "mañana" in normalized:
        return reference_date + timedelta(days=1)

    day_names = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
        "lunes": 0,
        "martes": 1,
        "miercoles": 2,
        "miércoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sabado": 5,
        "sábado": 5,
        "domingo": 6,
    }

    for day_name, day_num in day_names.items():
        if day_name in normalized:
            days_ahead = (day_num - reference_date.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return reference_date + timedelta(days=days_ahead)

    if "next" in normalized:
        for day_name, day_num in day_names.items():
            if day_name in normalized:
                days_ahead = (day_num - reference_date.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                return reference_date + timedelta(days=days_ahead + 7)

    month_names = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    for month_name, month_num in month_names.items():
        if month_name in normalized:
            day_match = re.search(r"\b(\d{1,2})\b", normalized)
            if day_match:
                day = int(day_match.group(1))
                year = reference_date.year
                if month_num < reference_date.month or (month_num == reference_date.month and day < reference_date.day):
                    year += 1
                try:
                    return date(year, month_num, day)
                except ValueError:
                    pass

    date_patterns = [
        r"\b(\d{1,2})[/-](\d{1,2})[/-]?(\d{2,4})?\b",
        r"\b(\d{1,2})[/-](\d{1,2})\b",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, normalized)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            year = int(match.group(3)) if match.lastindex >= 3 and match.group(3) else reference_date.year
            if year < 100:
                year += 2000
            if month < reference_date.month or (month == reference_date.month and day < reference_date.day):
                year += 1
            try:
                return date(year, month, day)
            except ValueError:
                pass

    return None


def parse_time_preference(text: str) -> tuple[int, int] | None:
    """Parse time preference from text. Returns (hour, minute) or None."""
    normalized = text.lower().strip()

    time_patterns = [
        r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b",
        r"\b(\d{1,2})\s*(am|pm)\b",
    ]

    for pattern in time_patterns:
        match = re.search(pattern, normalized)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.lastindex >= 2 and match.group(2).isdigit() else 0
            am_pm = match.group(match.lastindex) if match.lastindex >= 2 and match.group(match.lastindex) in ("am", "pm") else None

            if am_pm == "pm" and hour != 12:
                hour += 12
            elif am_pm == "am" and hour == 12:
                hour = 0

            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return (hour, minute)

    return None


def map_vague_time_to_range(vague_time: str) -> tuple[int, int] | None:
    """Map vague time description to hour range. Returns (start_hour, end_hour) or None."""
    normalized = vague_time.lower().strip()
    return VAGUE_TIME_RANGES.get(normalized)

