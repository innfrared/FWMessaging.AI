from __future__ import annotations

import re

YES_NO_PATTERNS = (
    "is there",
    "do you",
    "are you",
    "can i",
    "do you accept",
    "do you offer",
)

SERVICE_EXISTENCE_PATTERNS = (
    "do you offer",
    "do you do",
    "do you provide",
)


def normalize_text(text: str) -> str:
    normalized = text.lower().replace("+", " ")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def is_yes_no_question(text: str) -> bool:
    normalized = normalize_text(text)
    normalized = _strip_greeting(normalized)
    return any(normalized.startswith(pattern) for pattern in YES_NO_PATTERNS)


def is_service_existence_question(text: str) -> bool:
    normalized = normalize_text(text)
    return any(pattern in normalized for pattern in SERVICE_EXISTENCE_PATTERNS)


def extract_service_query(text: str) -> str | None:
    normalized = normalize_text(text)
    for pattern in SERVICE_EXISTENCE_PATTERNS:
        if pattern in normalized:
            tail = normalized.split(pattern, 1)[-1].strip()
            return tail if tail else None
    return None


def is_brazilian_query(text: str) -> bool:
    return "brazilian" in normalize_text(text)


def contains_location_request(text: str) -> bool:
    normalized = normalize_text(text)
    return any(term in normalized for term in ("location", "address", "where", "located"))


def is_booking_request(text: str) -> bool:
    """
    Check if user explicitly requests to book or schedule.
    Requires schedule verbs or appointment keywords, not just "session".
    """
    normalized = normalize_text(text)
    booking_verbs = (
        "book",
        "schedule",
        "appointment",
        "reserve",
        "reservar",
        "agendar",
        "cita",
    )
    
    booking_patterns = (
        "i would like to book",
        "i want to book",
        "i would like to schedule",
        "i want to schedule",
        "ready to book",
        "i want to make an appointment",
        "i would like to make an appointment",
        "can i schedule",
        "can i book",
        "would like to schedule",
        "want to schedule",
        "make an appointment",
        "set up an appointment",
    )
    
    has_booking_verb = any(verb in normalized for verb in booking_verbs)
    has_booking_pattern = any(pat in normalized for pat in booking_patterns)
    
    return has_booking_verb or has_booking_pattern


def _strip_greeting(text: str) -> str:
    greetings = ("hi", "hello", "hey", "hola")
    parts = text.split()
    while parts and parts[0] in greetings:
        parts = parts[1:]
    return " ".join(parts)


def has_explicit_price_intent(text: str) -> bool:
    """
    Check if user explicitly asks about price, cost, or "how much".
    Pricing blocks should ONLY be included if this returns True.
    """
    normalized = normalize_text(text)
    price_keywords = (
        "price",
        "pricing",
        "cost",
        "how much",
        "how many",
        "cuanto",
        "precio",
        "costo",
        "cuánto",
        "$",
        "dollar",
        "dollars",
    )
    return any(keyword in normalized for keyword in price_keywords)


def has_equipment_intent(text: str) -> bool:
    """
    Check if user asks about equipment/machine.
    """
    normalized = normalize_text(text)
    equipment_keywords = (
        "machine",
        "equipment",
        "laser machine",
        "what laser",
        "which laser",
        "maquina",
        "equipo",
    )
    return any(keyword in normalized for keyword in equipment_keywords)


def asks_about_sessions(text: str) -> bool:
    """
    Check if user asks about number of sessions, frequency, or duration.
    """
    normalized = normalize_text(text)
    session_keywords = (
        "how many times",
        "how many sessions",
        "how often",
        "how long does it take",
        "how many do i need",
        "how many visits",
        "cuantas veces",
        "cuantas sesiones",
        "cuanto tiempo",
    )
    return any(keyword in normalized for keyword in session_keywords)


def asks_about_duration(text: str) -> bool:
    """
    Check if user asks about appointment duration or how long a service takes.
    """
    normalized = normalize_text(text)
    duration_keywords = (
        "how long does it take",
        "how long is",
        "what is the duration",
        "how much time",
        "how long should i expect",
        "how long is the appointment",
        "cuanto tiempo toma",
        "cuanto dura",
        "duracion",
        "duración",
    )
    return any(keyword in normalized for keyword in duration_keywords)


def is_informational_question(text: str) -> bool:
    """
    Check if user is asking an informational question that should NOT trigger booking flow.
    These are questions about results, outcomes, what to expect, etc.
    """
    normalized = normalize_text(text)
    informational_patterns = (
        "will i see",
        "will i get",
        "will i have",
        "what will",
        "what should i expect",
        "what to expect",
        "when will i see",
        "when will i get",
        "how long until",
        "how long before",
        "when do i see",
        "when do i get",
        "results after",
        "results from",
        "outcome",
        "effectiveness",
        "how effective",
        "what happens",
        "what to expect",
        "que esperar",
        "cuando vere",
        "cuando tendre",
        "resultados",
    )
    return any(pattern in normalized for pattern in informational_patterns)


def asks_about_results(text: str) -> bool:
    """
    Check if user asks about results, outcomes, or effectiveness.
    This is a more specific version of informational questions focused on results.
    """
    normalized = normalize_text(text)
    results_patterns = (
        "see results",
        "get results",
        "have results",
        "results after",
        "results from",
        "results with",
        "when will i see",
        "when do i see",
        "when will i get",
        "when do i get",
        "after first session",
        "after one session",
        "after 1 session",
        "how many sessions until",
        "sessions until",
        "does it work after",
        "work after one",
        "work after 1",
        "effective after",
        "resultados",
        "cuando vere resultados",
        "cuando tendre resultados",
        "despues de la primera sesion",
    )
    return any(pattern in normalized for pattern in results_patterns)


def contains_date_or_time(text: str) -> bool:
    """
    Check if message contains date or time information that could be a booking response.
    Used to detect if user is replying to a booking question with date/time.
    """
    normalized = normalize_text(text)
    
    date_keywords = (
        "today",
        "tomorrow",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "next week",
        "next month",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "hoy",
        "mañana",
        "lunes",
        "martes",
        "miercoles",
        "miércoles",
        "jueves",
        "viernes",
        "sabado",
        "sábado",
        "domingo",
    )
    
    time_keywords = (
        "am",
        "pm",
        "morning",
        "afternoon",
        "evening",
        "night",
        "mañana",
        "tarde",
        "noche",
    )
    
    time_pattern = re.search(r"\d{1,2}\s*(am|pm|:\d{2})", normalized)
    
    has_date = any(keyword in normalized for keyword in date_keywords)
    has_time = any(keyword in normalized for keyword in time_keywords) or time_pattern is not None
    
    return has_date or has_time
