#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.application.use_cases.reply_composer import ReplyComposer
from app.infrastructure.knowledge.structured_kb import build_kb


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"FAILED: {label}")
    print(f"OK: {label}")


def assert_not_contains(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"FAILED: {label}")
    print(f"OK: {label}")


def assert_equals(text: str, expected: str, label: str) -> None:
    if text != expected:
        raise AssertionError(f"FAILED: {label} (got: {text!r}, expected: {expected!r})")
    print(f"OK: {label}")


def count_emojis(text: str, allowed: set[str]) -> int:
    return sum(1 for char in text if char in allowed)


def main() -> None:
    kb = build_kb()
    composer = ReplyComposer(kb=kb)

    reply = composer.compose(
        intent="services_list",
        resolved_service=None,
        language="en",
        greeting_applicable=True,
        yesno_answer=None,
    )
    assert_contains(reply.text, "Hi 🤍", "greeting is exactly 'Hi 🤍'")
    assert_contains(reply.text, "We offer:", "services list header")
    assert_contains(reply.text, "• Laser Hair Removal", "services list contains laser")
    assert_contains(reply.text, "Which service are you interested in? ✨", "services list CTA")
    assert_not_contains(reply.text, "—", "no em dash")
    assert_not_contains(reply.text.lower(), "love", "no banned word 'love'")
    assert_not_contains(reply.text.lower(), "hun", "no banned word 'hun'")
    assert_not_contains(reply.text.lower(), "babe", "no banned word 'babe'")
    assert_not_contains(reply.text.lower(), "sweetie", "no banned word 'sweetie'")
    allowed_emojis = {"🤍", "✨", "☀️"}
    emoji_count = count_emojis(reply.text, allowed_emojis)
    assert_equals(emoji_count <= 2, True, f"emoji count <= 2 (got {emoji_count})")
    disallowed = {"💕", "💆", "📍"}
    for emoji in disallowed:
        assert_not_contains(reply.text, emoji, f"no disallowed emoji {emoji}")

    reply = composer.compose(
        intent="pricing",
        resolved_service="facial + deep blackhead removal",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
    )
    assert_contains(reply.text, "LIMITED TIME PROMO", "facial promo header")
    assert_contains(reply.text, "Pricing: $120–$150", "facial price range with colon")
    assert_not_contains(reply.text, "—", "no em dash")
    assert_not_contains(reply.text, "💆", "no disallowed emoji")

    reply = composer.compose(
        intent="availability",
        resolved_service="facial + deep blackhead removal",
        language="en",
        greeting_applicable=False,
        yesno_answer="Yes, we have availability for Facial + Deep Blackhead Removal.",
    )
    assert_contains(reply.text, "Yes, we have availability", "availability yes line with comma")
    assert_not_contains(reply.text, "Yes hun", "no 'hun' in yes answer")
    assert_contains(reply.text, "What day and time works for you? ✨", "day time CTA")
    assert_not_contains(reply.text, "—", "no em dash")

    reply = composer.compose(
        intent="services_list",
        resolved_service=None,
        language="es",
        greeting_applicable=True,
        yesno_answer=None,
    )
    assert_contains(reply.text, "Hola 🤍", "spanish greeting is exactly 'Hola 🤍'")
    assert_contains(reply.text, "Ofrecemos:", "spanish services list header")
    assert_contains(reply.text, "Que servicio te interesa? ✨", "spanish services list CTA")

    reply = composer.compose(
        intent="services_list",
        resolved_service=None,
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
    )
    assert_contains(reply.text, "We offer:", "services list shown when no yes/no answer")
    assert_not_contains(reply.text.lower(), "no", "never says 'no'")
    assert_not_contains(reply.text.lower(), "don't offer", "never says 'don't offer'")


    reply = composer.compose(
        intent="services_list",
        resolved_service=None,
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
    )
    cta_count = reply.text.count("Which service are you interested in? ✨")
    assert_equals(cta_count, 1, "exactly one CTA in services list reply")

    reply = composer.compose(
        intent="booking",
        resolved_service="facial + deep blackhead removal",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
    )
    assert_contains(reply.text, "Would you like to book a time? ✨", "booking CTA")
    assert_not_contains(reply.text, "—", "no em dash")

    reply = composer.compose(
        intent="location",
        resolved_service=None,
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
    )
    assert_contains(reply.text, "375 N First St", "location address")
    assert_not_contains(reply.text, "📍", "no location pin emoji")

    reply = composer.compose(
        intent="pricing",
        resolved_service="jawline",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
    )
    assert_contains(reply.text, "Jawline", "jawline service name")
    assert_contains(reply.text, "Pricing: $30", "jawline price $30")
    assert_not_contains(reply.text, "—", "no em dash in jawline reply")
    cta_count = reply.text.count("🤍")
    assert_equals(cta_count <= 2, True, f"emoji count <= 2 (got {cta_count})")

    reply = composer.compose(
        intent="pricing",
        resolved_service="pmu lips",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
    )
    assert_contains(reply.text, "PMU – Lips", "PMU lips service name")
    assert_contains(reply.text, "Pricing: $300", "PMU lips price $300")
    assert_not_contains(reply.text, "—", "no em dash")

    reply = composer.compose(
        intent="pricing",
        resolved_service="eyebrow tinting",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
    )
    assert_contains(reply.text, "Eyebrow Tinting", "eyebrow tinting service name")
    assert_contains(reply.text, "Pricing: $85", "eyebrow tinting price $85")

    reply = composer.compose(
        intent="pricing",
        resolved_service="microdermabrasion",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
    )
    assert_contains(reply.text, "Microdermabrasion", "microdermabrasion service name")
    assert_contains(reply.text, "Pricing: $180", "microdermabrasion price $180")

    reply = composer.compose(
        intent="pricing",
        resolved_service="full upper body diode laser men",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
    )
    assert_contains(reply.text, "Full Upper Body Diode Laser (Men)", "men full upper body service name")
    assert_contains(reply.text, "Pricing: $250", "men full upper body price $250")

    reply = composer.compose(
        intent="pricing",
        resolved_service="full face laser",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
    )
    assert_contains(reply.text, "Full Face Laser", "full face laser service name")
    assert_contains(reply.text, "Pricing: $50", "full face laser price $50")
    assert_contains(reply.text, "Add-on with Full Body only", "full face laser add-on constraint")

    reply = composer.compose(
        intent="services_list",
        resolved_service=None,
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
    )
    assert_contains(reply.text, "• Combo Services", "services list includes Combo Services")

    reply = composer.compose(
        intent="services_list",
        resolved_service=None,
        language="es",
        greeting_applicable=False,
        yesno_answer=None,
    )
    assert_contains(reply.text, "• Servicios Combinados", "spanish services list includes Servicios Combinados")

    resolved = kb.resolve_service_from_text("How much is jawline laser?")
    assert_equals(resolved, "jawline", "jawline resolves correctly")

    resolved = kb.resolve_service_from_text("PMU lips price?")
    assert_equals(resolved, "pmu lips", "PMU lips resolves correctly")

    resolved = kb.resolve_service_from_text("brow tint?")
    assert_equals(resolved, "eyebrow tinting", "brow tint resolves to eyebrow tinting")

    resolved = kb.resolve_service_from_text("full body diode laser")
    assert_equals(resolved, "full body diode laser", "full body diode laser resolves correctly")

    resolved = kb.resolve_service_from_text("Do you do Brazilian?")
    assert_equals(resolved, "brazilian bikini", "Brazilian resolves to brazilian bikini")

    ambiguous = kb.is_ambiguous_category_question("How much is laser?")
    assert_equals(ambiguous, "laser", "Ambiguous laser question detected")

    ambiguous2 = kb.is_ambiguous_category_question("laser")
    assert_equals(ambiguous2, "laser", "Single word 'laser' detected as ambiguous")

    ambiguous3 = kb.is_ambiguous_category_question("laser price")
    assert_equals(ambiguous3, "laser", "Short laser query detected as ambiguous")

    ambiguous4 = kb.is_ambiguous_category_question("How much is jawline laser?")
    assert_equals(ambiguous4, None, "Specific laser query (jawline) is not ambiguous")

    ambiguous5 = kb.is_ambiguous_category_question("full body laser price")
    assert_equals(ambiguous5, None, "Specific laser query (full body) is not ambiguous")

    resolved = kb.resolve_service_from_text("Facial and lash lamination price?")
    assert_equals(resolved, "facial blackhead removal lash lamination", "Combo service takes precedence over individual services")

    resolved2 = kb.resolve_service_from_text("facial + lash lamination")
    assert_equals(resolved2, "facial blackhead removal lash lamination", "Combo service with + takes precedence")

    reply = composer.compose(
        intent="laser_clarification",
        resolved_service=None,
        language="en",
        greeting_applicable=True,
        yesno_answer=None,
    )
    assert_contains(reply.text, "Laser Hair Removal pricing depends on the area", "laser clarification explains pricing depends on area")
    assert_contains(reply.text, "Laser Hair Removal pricing depends on the area", "laser clarification explains pricing depends on area")
    assert_contains(reply.text, "• Full Body", "laser clarification lists Full Body")
    assert_contains(reply.text, "• Face", "laser clarification lists Face")
    assert_contains(reply.text, "• Men's Laser Services", "laser clarification lists Men's services")
    assert_contains(reply.text, "Which area are you interested in? ✨", "laser clarification has correct CTA")
    assert_not_contains(reply.text, "—", "laser clarification has no em dash")

    reply = composer.compose(
        intent="pricing",
        resolved_service="facial blackhead removal lash lamination",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
    )
    assert_contains(reply.text, "Facial (Blackhead Removal) + Lash Lamination", "combo service name correct")
    assert_contains(reply.text, "Pricing: $155", "combo service price $155")

    print("\nAll tests passed! ✅")


def test_pricing_gating():
    """Test that pricing is only included when user explicitly asks for price."""
    kb = build_kb()
    composer = ReplyComposer(kb=kb)
    
    # Test 1: Availability-only question → no pricing
    reply = composer.compose(
        intent="availability",
        resolved_service="eyebrow lamination",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=False,
    )
    assert_not_contains(reply.text, "Pricing:", "availability question should not include pricing")
    assert_not_contains(reply.text, "$85", "availability question should not include price")
    
    # Test 2: Availability + equipment → no pricing
    reply = composer.compose(
        intent="availability",
        resolved_service="eyebrow lamination",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=False,
        include_equipment=True,
    )
    assert_not_contains(reply.text, "Pricing:", "availability + equipment should not include pricing")
    assert_contains(reply.text, "DM40P", "equipment info should be included")
    
    # Test 3: Explicit price question → pricing allowed
    reply = composer.compose(
        intent="pricing",
        resolved_service="eyebrow lamination",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
    )
    assert_contains(reply.text, "Pricing:", "explicit price question should include pricing")
    assert_contains(reply.text, "$85", "explicit price question should include price")
    
    # Test 4: Service resolution without price intent → no pricing
    reply = composer.compose(
        intent="service_details",
        resolved_service="eyebrow lamination",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=False,
    )
    assert_not_contains(reply.text, "Pricing:", "service_details without price intent should not include pricing")
    
    print("OK: pricing gating")


def test_session_facts_enrichment():
    """Test that session facts are added when user asks about sessions."""
    kb = build_kb()
    composer = ReplyComposer(kb=kb)

    reply = composer.compose(
        intent="pricing",
        resolved_service="full body diode laser",
        language="en",
        greeting_applicable=True,
        yesno_answer=None,
        explicit_price_intent=True,
        include_session_facts=True,
    )
    assert_contains(reply.text, "Pricing: $150", "pricing + sessions includes pricing")
    assert_contains(reply.text, "Most clients need about 6 sessions", "pricing + sessions includes session facts")

    reply = composer.compose(
        intent="pricing",
        resolved_service="full body diode laser",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
        include_session_facts=False,
    )
    assert_contains(reply.text, "Pricing: $150", "pricing-only includes pricing")
    assert_not_contains(reply.text, "Most clients need about 6 sessions", "pricing-only does not include session text")

    reply = composer.compose(
        intent="availability",
        resolved_service="full body diode laser",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=False,
        include_session_facts=True,
    )
    assert_not_contains(reply.text, "Most clients need about 6 sessions", "session facts don't appear without pricing")

    reply = composer.compose(
        intent="pricing",
        resolved_service="full body diode laser",
        language="en",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
        include_session_facts=True,
    )
    pricing_count = reply.text.count("Pricing:")
    assert_equals(pricing_count, 1, "pricing appears exactly once")
    service_name_count = reply.text.count("Full Body Diode Laser")
    assert_equals(service_name_count <= 2, True, "service name not duplicated beyond allowed")

    allowed_emojis = {"🤍", "✨", "☀️"}
    emoji_count = sum(1 for char in reply.text if char in allowed_emojis)
    assert_equals(emoji_count <= 2, True, f"emoji count <= 2 (got {emoji_count})")

    reply = composer.compose(
        intent="pricing",
        resolved_service="full body diode laser",
        language="es",
        greeting_applicable=False,
        yesno_answer=None,
        explicit_price_intent=True,
        include_session_facts=True,
    )
    assert_contains(reply.text, "La mayoría de los clientes", "spanish session facts included")

    print("OK: session facts enrichment")


if __name__ == "__main__":
    main()
    test_pricing_gating()
    test_session_facts_enrichment()
    print("\nAll tests passed! ✅")
