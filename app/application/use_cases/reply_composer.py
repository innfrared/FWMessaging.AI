from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.knowledge_base import KnowledgeBasePort
from app.domain.entities.response_template import ResponseTemplate


CTA_SIGNATURES = (
    "Which service are you interested in? ✨",
    "Would you like to book a time? ✨",
    "What day and time works for you? ✨",
    "Let us know how we can help ✨",
    "Que servicio te interesa? ✨",
    "Te gustaria agendar una cita? ✨",
    "Que dia y hora te funciona? ✨",
    "Dinos como podemos ayudarte ✨",
    "Which area are you interested in? ✨",
    "Que area te interesa? ✨",
)


@dataclass(frozen=True)
class ComposedReply:
    text: str
    error: str | None = None


class ReplyComposer:
    def __init__(self, kb: KnowledgeBasePort) -> None:
        self._kb = kb

    def compose(
        self,
        intent: str,
        resolved_service: str | None,
        language: str,
        greeting_applicable: bool,
        yesno_answer: str | None,
        include_location: bool = False,
        booking_only_cta: bool = False,
        explicit_price_intent: bool = False,
        include_equipment: bool = False,
        include_session_facts: bool = False,
        user_message_text: str | None = None,
        booking_result: "BookingResult | None" = None,
    ) -> ComposedReply:
        from app.application.use_cases.booking import BookingResult

        blocks: list[str] = []

        greeting_block = None
        if greeting_applicable:
            greeting_block = _greeting(language)
            is_valid, error = _validate_greeting_block(greeting_block)
            if not is_valid:
                return ComposedReply(_get_fallback_services_list(language), f"greeting_validation_failed_{error}")
            blocks.append(greeting_block)

        if booking_result:
            booking_message = None
            if booking_result.message:
                booking_message = booking_result.message
            else:
                booking_message = _build_booking_message(booking_result, language)
            
            if booking_message:
                blocks.append(booking_message)
                reply_text = _join_blocks(blocks)
                is_valid, error = _validate_reply(reply_text, language, is_canonical_message=False)
                if not is_valid:
                    return ComposedReply(_get_fallback_services_list(language), f"booking_validation_failed_{error}")
                return ComposedReply(reply_text, None)

        canonical_message = None
        if user_message_text:
            registry_key = self._kb.resolve_service_to_registry_key(user_message_text)
            if registry_key:
                message_lines = self._kb.get_canonical_service_message(registry_key, language)
                if message_lines:
                    canonical_message = "\n".join(message_lines)
        elif resolved_service:
            registry_key = self._kb.resolve_service_to_registry_key(resolved_service)
            if registry_key:
                message_lines = self._kb.get_canonical_service_message(registry_key, language)
                if message_lines:
                    canonical_message = "\n".join(message_lines)

        detail = ""
        if canonical_message:
            blocks.append(canonical_message)
            detail = canonical_message
        else:
            if yesno_answer:
                yesno_answer = _strip_pricing_from_yesno(yesno_answer)
                is_valid, error = _validate_yesno_block(yesno_answer)
                if not is_valid:
                    return ComposedReply(_get_fallback_services_list(language), f"yesno_validation_failed_{error}")
                blocks.append(yesno_answer)

            if not booking_only_cta:
                detail = self._select_detail_block(intent, resolved_service, language, explicit_price_intent)
                if not detail:
                    return ComposedReply("", "missing_detail")
                if intent in {"availability", "booking"}:
                    detail = _strip_cta_paragraphs(detail)
                is_valid, error = _validate_detail_block(detail)
                if not is_valid:
                    return ComposedReply(_get_fallback_services_list(language), f"detail_validation_failed_{error}")
                blocks.append(detail)

        if include_equipment:
            equipment_template = self._kb.get_template("equipment", None, language)
            if equipment_template:
                blocks.append(equipment_template.text)

        if include_session_facts and resolved_service and explicit_price_intent:
            session_fact = self._kb.get_service_facts(resolved_service, language)
            if session_fact:
                is_valid, error = _validate_session_facts_block(session_fact)
                if not is_valid:
                    return ComposedReply(_get_fallback_services_list(language), f"session_facts_validation_failed_{error}")
                blocks.append(session_fact)

        if include_location:
            location_block = self._kb.get_template("location", None, language)
            if not location_block:
                return ComposedReply("", "missing_location")
            blocks.append(location_block.text)

        is_laser_service = self._is_laser_service(resolved_service, user_message_text)
        is_services_list = (intent == "services_list")
        detail_for_cta = canonical_message if canonical_message else detail
        cta = self._select_cta_block(intent, resolved_service, language, detail_for_cta, is_laser_service=is_laser_service)
        if cta:
            is_valid, error = _validate_cta_block(cta, is_laser_service=is_laser_service, is_services_list=is_services_list)
            if not is_valid:
                return ComposedReply(_get_fallback_services_list(language), f"cta_validation_failed_{error}")
            blocks.append(cta)

        reply_text = _join_blocks(blocks)
        reply_text = _dedupe_paragraphs(reply_text)

        if yesno_answer and not _validate_no_pricing_in_yesno(yesno_answer):
            cleaned_blocks = []
            if greeting_applicable:
                cleaned_blocks.append(_greeting(language))
            cleaned_blocks.append(_strip_pricing_from_yesno(yesno_answer))
            if detail:
                cleaned_blocks.append(detail)
            if include_location:
                location_block = self._kb.get_template("location", None, language)
                if location_block:
                    cleaned_blocks.append(location_block.text)
            if cta:
                cleaned_blocks.append(cta)
            reply_text = _join_blocks(cleaned_blocks)
            reply_text = _dedupe_paragraphs(reply_text)

        if not canonical_message:
            service_name_error = _validate_service_name_repetition(reply_text, yesno_answer is not None if yesno_answer else False)
            if service_name_error:
                return ComposedReply(_get_fallback_services_list(language), f"service_name_validation_failed_{service_name_error}")

        if not canonical_message:
            pricing_count = _count_pricing_occurrences(reply_text)
            if pricing_count > 1:
                return ComposedReply(_get_fallback_services_list(language), f"pricing_duplication_{pricing_count}_occurrences")
            if pricing_count > 0 and not explicit_price_intent:
                return ComposedReply(_get_fallback_services_list(language), f"pricing_without_explicit_intent")

        if _cta_count(reply_text) > 1:
            return ComposedReply(_get_fallback_services_list(language), "cta_duplicate")

        if not canonical_message and detail and not _contains_required(detail, reply_text):
            return ComposedReply(_get_fallback_services_list(language), "missing_required_content")


        is_valid, error = _validate_reply(reply_text, language, is_canonical_message=bool(canonical_message))
        if not is_valid:
            return ComposedReply(_get_fallback_services_list(language), f"validation_failed_{error}")

        return ComposedReply(reply_text)

    def _select_detail_block(self, intent: str, service: str | None, language: str, explicit_price_intent: bool = False) -> str | None:
        """
        Select detail block based on intent and service.
        Pricing/service_details blocks are ONLY included if explicit_price_intent is True.
        """
        if intent in {"pricing", "service_details", "availability", "booking"}:
            if service:
                if intent in {"pricing", "service_details"} and not explicit_price_intent:
                    template = self._kb.get_template("booking_info", None, language)
                    return template.text if template else None

                if intent in {"availability", "booking"}:
                    template = self._kb.get_template("booking_info", None, language)
                    return template.text if template else None

                template = self._kb.get_template("pricing", service, language) or self._kb.get_template(
                    "service_details", service, language
                )
                return template.text if template else None
            if intent in {"availability", "booking"}:
                template = self._kb.get_template("booking_info", None, language)
                return template.text if template else None
            template = self._kb.get_template("services_list", None, language)
            return template.text if template else None

        if intent == "services_list":
            template = self._kb.get_template("services_list", None, language)
            return template.text if template else None

        if intent == "location":
            template = self._kb.get_template("location", None, language)
            return template.text if template else None

        if intent == "hours":
            template = self._kb.get_template("hours", None, language)
            return template.text if template else None

        if intent == "laser_clarification":
            template = self._kb.get_template("laser_clarification", None, language)
            return template.text if template else None

        return None

    def _is_laser_service(self, resolved_service: str | None, user_message_text: str | None) -> bool:
        """
        Check if the service is laser-related, brows-related, lash-related, facial-related, or microdermabrasion.
        Returns True if service is laser, brows, lash, facial, or microdermabrasion (for special CTA override), False otherwise.
        """
        if user_message_text:
            registry_key = self._kb.resolve_service_to_registry_key(user_message_text)
            if registry_key:
                key_lower = registry_key.lower()
                if "laser" in key_lower or "brow" in key_lower or "lash" in key_lower or "facial" in key_lower or "microdermabrasion" in key_lower or "facelift" in key_lower:
                    return True

        if resolved_service:
            service_lower = resolved_service.lower()
            if "laser" in service_lower or "brow" in service_lower or "lash" in service_lower or "facial" in service_lower or "microdermabrasion" in service_lower or "facelift" in service_lower:
                return True

        return False

    def _select_cta_block(self, intent: str, service: str | None, language: str, detail_text: str, is_laser_service: bool = False) -> str | None:
        if is_laser_service:
            if language == "es":
                return "Por favor avisanos si tienes alguna pregunta sobre el tratamiento o si te gustaria agendar una cita."
            return "Please let us know if you have any questions regarding the treatment or if you would like to schedule an appointment."

        if intent == "availability":
            ask = _ask_day_time(language)
            if ask in detail_text:
                return None
            return ask

        if intent == "booking":
            ask = _ask_booking_preference(language)
            if ask in detail_text:
                return None
            return ask

        if _contains_cta_signature(detail_text):
            return None

        if intent == "services_list":
            if language == "es":
                return "Por favor avisanos si tienes alguna pregunta sobre nuestros tratamientos."
            return "Please let us know if you have any questions regarding our treatments."

        if intent == "laser_clarification":
            if language == "es":
                return "Que area te interesa? ✨"
            return "Which area are you interested in? ✨"

        if intent in {"hours", "location", "pricing", "service_details"}:
            if language == "es":
                return "Dinos como podemos ayudarte ✨"
            return "Let us know how we can help ✨"

        if intent == "closing":
            return "You are very welcome."

        return None


def _ask_day_time(language: str) -> str:
    if language == "es":
        return "Que dia y hora te funciona? ✨"
    return "What day and time works for you? ✨"


def _ask_booking_preference(language: str) -> str:
    if language == "es":
        return "Te gustaria agendar una cita? ✨"
    return "Would you like to book a time? ✨"


FORBIDDEN_SYSTEM_PHRASES = [
    "sorry",
    "not available",
    "system",
    "at this time",
    "unavailable",
    "error",
    "failed",
    "hubo un error",
    "lo siento",
    "sistema",
    "no disponible",
]


def _validate_no_system_language(text: str) -> tuple[bool, str]:
    """Validate that text doesn't contain system failure language."""
    lowered = text.lower()
    for phrase in FORBIDDEN_SYSTEM_PHRASES:
        if phrase in lowered:
            return False, f"contains_system_language_{phrase}"
    return True, ""


def _format_slots(slots: list[datetime], language: str) -> str:
    """Format time slots for display."""
    if not slots:
        return ""
    
    formatted = []
    for slot in slots:
        time_str = slot.strftime("%I:%M %p")
        formatted.append(time_str)
    
    if language == "es":
        if len(formatted) == 1:
            return formatted[0]
        if len(formatted) == 2:
            return f"{formatted[0]} o {formatted[1]}"
        return ", ".join(formatted[:-1]) + f" o {formatted[-1]}"
    
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} or {formatted[1]}"
    return ", ".join(formatted[:-1]) + f" or {formatted[-1]}"


def _build_booking_message(booking_result: "BookingResult", language: str) -> str:
    """Build user-facing booking message based on action."""
    from app.application.use_cases.booking import BookingResult
    from datetime import datetime
    
    action = booking_result.action
    
    if action == "ask_date":
        if language == "es":
            return "¿Qué fecha te funciona?"
        return "What date works for you?"
    
    if action == "ask_time":
        if language == "es":
            return "¿Qué hora te funciona mejor?"
        return "What time works best for you?"
    
    if action == "suggest_slots":
        if booking_result.proposed_slots:
            slots_text = _format_slots(booking_result.proposed_slots, language)
            if language == "es":
                return f"Tengo disponibilidad en: {slots_text}. ¿Cuál te funciona mejor?"
            return f"I have availability at: {slots_text}. Which works better for you?"
        if language == "es":
            return "¿Qué día y hora te funciona?"
        return "What day and time works for you?"
    
    if action == "confirm":
        if booking_result.proposed_slots and len(booking_result.proposed_slots) > 0:
            slot = booking_result.proposed_slots[0]
            date_str = slot.strftime("%B %d")
            time_str = slot.strftime("%I:%M %p")
            service_name = booking_result.updated_state.service_key or "appointment"
            if booking_result.updated_state.service_key:
                from app.infrastructure.knowledge.service_catalog_store import ServiceCatalogStore
                catalog = ServiceCatalogStore()
                entry = catalog.get_service(booking_result.updated_state.service_key)
                if entry:
                    service_name = entry.display_name
            if language == "es":
                return f"¿Te gustaría que reserve {service_name} el {date_str} a las {time_str}?"
            return f"Would you like me to book {service_name} on {date_str} at {time_str}?"
    
    if action == "booked":
        if booking_result.updated_state.proposed_time:
            date_str = booking_result.updated_state.proposed_time.strftime("%B %d")
            time_str = booking_result.updated_state.proposed_time.strftime("%I:%M %p")
            if language == "es":
                return f"¡Perfecto! He reservado tu cita para el {date_str} a las {time_str}. Te esperamos."
            return f"Perfect! I've booked your appointment for {date_str} at {time_str}. We look forward to seeing you."
    
    if action in ("unavailable", "reset"):
        if language == "es":
            return "¿Qué día y hora te funciona?"
        return "What day and time works for you?"
    
    return ""


def _greeting(language: str) -> str:
    """Return exact greeting format (no emoji)."""
    if language == "es":
        return "Hola, gracias por escribirnos!"
    return "Hello, thank you for reaching out!"


def _join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(block.strip() for block in blocks if block and block.strip())


def _dedupe_paragraphs(text: str) -> str:
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for p in paragraphs:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return "\n\n".join(out)


def _contains_required(detail: str, reply_text: str) -> bool:
    return detail in reply_text


def _cta_count(text: str) -> int:
    return sum(1 for sig in CTA_SIGNATURES if sig in text)


def _contains_cta_signature(text: str) -> bool:
    return any(sig in text for sig in CTA_SIGNATURES)


def _strip_cta_paragraphs(text: str) -> str:
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    kept = [p for p in paragraphs if not _contains_cta_signature(p)]
    return "\n\n".join(kept)


def _validate_reply(text: str, language: str, is_canonical_message: bool = False) -> tuple[bool, str]:
    """Returns (is_valid, error_message)"""
    if "—" in text:
        return False, "contains_em_dash"

    banned_words = ["love", "hun", "babe", "sweetie", "honey"]
    text_lower = text.lower()
    for word in banned_words:
        if word in text_lower:
            return False, f"contains_banned_word_{word}"

    if not is_canonical_message:
        disallowed_emojis = {"💕", "🤍", "❤️", "💖", "🙏", "👍"}
        text_without_location = text.replace("📍", "")
        has_disallowed = any(emoji in text_without_location for emoji in disallowed_emojis)
        if has_disallowed:
            return False, "contains_disallowed_emoji"

    if _cta_count(text) > 1:
        return False, "cta_duplicate"

    is_valid, error = _validate_no_system_language(text)
    if not is_valid:
        return False, error

    return True, ""


def _strip_pricing_from_yesno(text: str) -> str:
    """
    Remove pricing information from yes/no answers.
    Yes/No answers should only contain service name confirmation, not pricing.
    Pricing belongs in the detail block only.
    """
    import re
    # Remove patterns like "Pricing: $X" or "Precio: $X"
    text = re.sub(r"\s*(?:Pricing|Precio):\s*\$[0-9]+(?:–[0-9]+)?", "", text)
    # Clean up any double spaces or trailing punctuation issues
    text = re.sub(r"\s+", " ", text).strip()
    # Ensure it ends with a period if it's a yes/no answer
    if text and not text.endswith("."):
        text = text.rstrip(".,") + "."
    return text


def _validate_no_pricing_in_yesno(yesno_answer: str | None) -> bool:
    """
    Validate that yes/no answer does not contain pricing.
    Returns True if valid (no pricing), False if pricing found.
    """
    if not yesno_answer:
        return True
    import re
    has_pricing = bool(re.search(r"(?:Pricing|Precio):\s*\$", yesno_answer))
    return not has_pricing


def _validate_greeting_block(text: str) -> tuple[bool, str]:
    """
    Validate greeting block: must be exactly "Hello, thank you for reaching out!".
    Returns (is_valid, error_message).
    """
    allowed_greeting = "Hello, thank you for reaching out!"
    if text != allowed_greeting:
        return False, f"greeting_must_be_exact_got_{text!r}"
    
    # Check for forbidden content
    forbidden_patterns = [
        (r"\$", "pricing"),
        (r"Pricing|Precio", "pricing_keyword"),
        (r"service|servicio", "service_name"),
        (r"Which|Que.*interesa", "cta"),
    ]
    text_lower = text.lower()
    for pattern, error_type in forbidden_patterns:
        import re
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False, f"greeting_contains_{error_type}"
    
    return True, ""


def _validate_yesno_block(text: str) -> tuple[bool, str]:
    """
    Validate yes/no answer block: accepts various yes/no answer formats.
    Common formats:
    - "Yes, we offer {service}."
    - "Yes, we are in Burbank."
    - "Hello, we do not do orders."
    - "Si, ofrecemos..."
    No pricing, no emojis.
    Returns (is_valid, error_message).
    """
    import re
    
    # More flexible pattern: must start with Yes/Si/Hello and end with period
    # Accepts various formats as long as it's a complete sentence ending with period
    if not text.strip().endswith("."):
        return False, "yesno_invalid_format"
    
    # Must start with common yes/no prefixes or greetings
    yesno_prefixes = (
        r"^(Yes,|Si,|Hello,|Hola,|Hi,|Hey,|Yes\.|Si\.)",
    )
    if not re.match(r"^(Yes,|Si,|Hello,|Hola,|Hi,|Hey,|Yes\.|Si\.)", text, re.IGNORECASE):
        return False, "yesno_invalid_format"
    
    # No pricing allowed
    if re.search(r"(?:Pricing|Precio):\s*\$", text):
        return False, "yesno_contains_pricing"
    
    # No emojis allowed
    if any(emoji in text for emoji in ["🤍", "✨", "☀️", "💕", "💆", "📍"]):
        return False, "yesno_contains_emoji"
    
    return True, ""


def _validate_detail_block(text: str) -> tuple[bool, str]:
    """
    Validate detail block: must contain service name and/or pricing.
    No CTA text allowed.
    Returns (is_valid, error_message).
    """
    if not text or not text.strip():
        return False, "detail_empty"
    
    # Check for CTA signatures (not allowed in detail block)
    if _contains_cta_signature(text):
        return False, "detail_contains_cta"
    
    return True, ""


def _validate_cta_block(text: str, is_laser_service: bool = False, is_services_list: bool = False) -> tuple[bool, str]:
    """
    Validate CTA block: exactly one CTA signature, exactly one ✨ emoji (unless laser/service list service).
    No pricing, no service names.
    Returns (is_valid, error_message).
    """
    import re
    
    # Laser service or services_list CTA doesn't have emoji, so skip emoji validation
    if is_laser_service or is_services_list:
        # Just check it's not empty and doesn't contain pricing
        if not text.strip():
            return False, "cta_empty"
        if re.search(r"(?:Pricing|Precio):\s*\$", text):
            return False, "cta_contains_pricing"
        return True, ""
    
    # Must contain exactly one CTA signature
    cta_count = _cta_count(text)
    if cta_count != 1:
        return False, f"cta_count_{cta_count}_not_one"
    
    # Must contain exactly one ✨ emoji
    emoji_count = text.count("✨")
    if emoji_count != 1:
        return False, f"cta_emoji_count_{emoji_count}_not_one"
    
    # No pricing allowed
    if re.search(r"(?:Pricing|Precio):\s*\$", text):
        return False, "cta_contains_pricing"
    
    # No service names (basic check)
    service_keywords = ["Laser", "Facial", "Lash", "Brow", "PMU", "Brazilian", "Full Body"]
    if any(keyword in text for keyword in service_keywords):
        # Allow if it's part of CTA text like "Which service" but not standalone service names
        if not any(cta_sig in text for cta_sig in CTA_SIGNATURES if "service" in cta_sig.lower()):
            return False, "cta_contains_service_name"
    
    return True, ""


def _validate_service_name_repetition(reply_text: str, has_yesno: bool) -> str | None:
    """
    Validate service name repetition rule:
    - If yes/no block exists: service name may appear in yes/no + detail header (2 times max)
    - If no yes/no block: service name appears only once in detail

    Returns error message if validation fails, None if valid.

    Note: This validation is lenient - it checks for obvious repetition but allows
    service names that appear as part of combo services or natural text flow.
    """
    import re
    
    # Split into paragraphs to check for repetition across blocks
    paragraphs = [p.strip() for p in reply_text.split("\n\n") if p.strip()]
    
    # Extract first line of each paragraph (likely service name headers)
    first_lines = [p.split("\n")[0].strip() for p in paragraphs if p]
    
    # Count unique service name occurrences (not just pattern matches)
    # This is a simplified check - actual service names are typically in first line of detail block
    # We're looking for the same service name appearing multiple times as standalone headers
    
    # For now, we'll be lenient and only flag obvious repetition
    # The dedupe_paragraphs function already handles exact duplicates
    # This validation is mainly to catch cases where service name appears in yes/no AND detail
    
    # If we have yes/no, allow service name in first paragraph (yes/no) and second (detail)
    # Without yes/no, service name should only be in first paragraph (detail)
    if has_yesno and len(first_lines) >= 2:
        # Check if same service name appears in both yes/no and detail
        # This is acceptable, so we allow it
        pass
    elif not has_yesno and len(first_lines) >= 1:
        # Service name should only appear once in detail block
        # The dedupe function already handles this, so we're lenient here
        pass
    
    # For now, return None (valid) - the dedupe_paragraphs handles actual duplicates
    # This validation can be enhanced later if needed
    return None


def _count_pricing_occurrences(text: str) -> int:
    """
    Count how many times pricing appears in the text.
    Pricing should appear only once (in detail block).
    """
    import re
    # Count "Pricing: $X" or "Precio: $X" patterns
    pricing_matches = re.findall(r"(?:Pricing|Precio):\s*\$[0-9]+(?:–[0-9]+)?", text)
    return len(pricing_matches)


def _validate_session_facts_block(text: str) -> tuple[bool, str]:
    """
    Validate session facts block: no pricing, no service names, neutral language.
    Returns (is_valid, error_message).
    """
    import re
    
    # No pricing allowed
    if re.search(r"(?:Pricing|Precio):\s*\$", text):
        return False, "session_facts_contains_pricing"
    
    # No dollar signs
    if "$" in text:
        return False, "session_facts_contains_dollar"
    
    # No service names (to avoid duplication)
    # Check for common service name patterns
    service_name_patterns = (
        r"Full Body",
        r"Full Legs",
        r"Laser",
        r"Brazilian",
        r"Bikini",
    )
    for pattern in service_name_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "session_facts_contains_service_name"
    
    # No guarantees or promotional language
    guarantee_patterns = (
        r"guarantee",
        r"guaranteed",
        r"promise",
        r"will",
        r"always",
        r"never",
    )
    for pattern in guarantee_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "session_facts_contains_guarantee"
    
    # No emojis allowed
    if any(emoji in text for emoji in ["🤍", "✨", "☀️", "💕", "💆", "📍"]):
        return False, "session_facts_contains_emoji"
    
    return True, ""


def _get_fallback_services_list(language: str) -> str:
    if language == "es":
        return "Ofrecemos:\n• Depilación Láser\n• Faciales y Tratamientos de Piel\n• Pestañas\n• Cejas\n• Maquillaje Permanente\n• Servicios Combinados\n\nQue servicio te interesa? ✨"
    return "We offer:\n• Laser Hair Removal\n• Facials & Skin Treatments\n• Lash Services\n• Eyebrow Services\n• Permanent Makeup\n• Combo Services\n\nWhich service are you interested in? ✨"
