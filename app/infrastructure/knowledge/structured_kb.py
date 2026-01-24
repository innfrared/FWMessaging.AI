from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.application.ports.knowledge_base import KnowledgeBasePort
from app.domain.entities.response_template import ResponseTemplate
from app.infrastructure.knowledge.service_registry import SERVICE_REGISTRY


class StructuredKnowledgeBase(KnowledgeBasePort):
    def __init__(
        self,
        data: dict[str, dict[str, dict[str, ResponseTemplate]]],
        aliases: dict[str, list[str]],
        display_names: dict[str, str],
        service_facts: dict[str, dict[str, str]] | None = None,
        service_registry: dict[str, dict[str, dict[str, list[str]] | list[str]]] | None = None,
    ) -> None:
        self._data = data
        self._aliases = aliases
        self._display_names = display_names
        self._service_facts = service_facts or {}
        self._service_registry = service_registry or SERVICE_REGISTRY

    def get_template(self, intent: str, service: str | None, language: str) -> ResponseTemplate | None:
        intent_bucket = self._data.get(intent, {})
        service_key = (service or "").strip().lower()
        lang = language if language in {"en", "es"} else "en"

        if service_key and service_key in intent_bucket:
            return intent_bucket[service_key].get(lang) or intent_bucket[service_key].get("en")
        if "_default" in intent_bucket:
            return intent_bucket["_default"].get(lang) or intent_bucket["_default"].get("en")
        return None

    def resolve_service_from_text(self, text: str) -> str | None:
        normalized = _normalize_text(text)

        candidates: list[tuple[str, str, int]] = []
        for service, aliases in self._aliases.items():
            for alias in aliases:
                alias_norm = _normalize_text(alias)
                candidates.append((service, alias_norm, len(alias_norm.split())))

        candidates.sort(key=lambda x: (-x[2], x[0]))

        for service, alias_norm, _ in candidates:
            if alias_norm in normalized:
                if len(alias_norm.split()) == 1 and len(normalized.split()) == 1:
                    generic_words = {"laser", "brow", "brows", "lash", "lashes", "facial", "pmu"}
                    if alias_norm not in generic_words:
                        return service
                else:
                    return service

        for service, alias_norm, _ in candidates:
            if _fuzzy_match(alias_norm, normalized):
                return service

        return None

    def get_service_facts(self, service: str, language: str) -> str | None:
        """
        Get service facts (e.g., session guidance) for a given service.
        Returns the fact text in the specified language, or None if not available.
        """
        service_key = (service or "").strip().lower()
        lang = language if language in {"en", "es"} else "en"

        if service_key in self._service_facts:
            facts = self._service_facts[service_key]
            return facts.get(lang) or facts.get("en")
        return None

    def get_canonical_service_message(self, service_key: str, language: str) -> list[str] | None:
        """
        Get canonical service message lines for a service registry key.
        Returns list of message lines, or None if not available.
        """
        if service_key not in self._service_registry:
            return None

        service_entry = self._service_registry[service_key]
        if "message" not in service_entry:
            return None

        messages = service_entry["message"]
        lang = language if language in {"en", "es"} else "en"

        if isinstance(messages, dict):
            return messages.get(lang) or messages.get("en")

        return None

    def resolve_service_to_registry_key(self, text: str) -> str | None:
        """
        Resolve user text to a service registry key using registry aliases.
        Prioritizes longest/most specific alias matches.
        Includes semantic alias buckets for common user wording.
        Returns registry key (e.g., "laser_hair_removal_full_body") or None.
        """
        normalized = _normalize_text(text)

        # Semantic alias buckets for common user wording
        semantic_buckets = {
            "facial_deep_blackhead_removal": [
                "deep clean",
                "deep cleaning",
                "deep cleanse",
                "exfoliate",
                "exfoliation",
                "exfoliating",
                "clean pores",
                "pores",
                "pore cleaning",
                "blackheads",
                "whiteheads",
                "clogged pores",
            ],
            "microdermabrasion": [
                "exfoliate my skin",
                "skin exfoliation",
                "rough texture",
                "skin resurfacing",
                "microderm",
                "microdermabrasion",
            ],
            "laser_hair_removal_face": [
                "razor bumps",
                "ingrowns on face",
                "chin hair",
                "upper lip hair",
                "face hair",
                "facial hair",
            ],
        }

        # Check semantic buckets first (more specific)
        for registry_key, semantic_aliases in semantic_buckets.items():
            for semantic_alias in semantic_aliases:
                if semantic_alias in normalized:
                    # Prefer facial_deep_blackhead_removal over microdermabrasion for "exfoliate" unless "microderm" explicitly mentioned
                    if "exfoliate" in normalized and "microderm" not in normalized:
                        if registry_key == "microdermabrasion":
                            continue
                    return registry_key

        # Build candidates from registry aliases
        candidates: list[tuple[str, str, int, bool]] = []  # (key, alias, length, is_exact_phrase)
        for registry_key, entry in self._service_registry.items():
            aliases = entry.get("aliases", [])
            for alias in aliases:
                alias_norm = _normalize_text(alias)
                is_exact_phrase = len(alias_norm.split()) > 1
                candidates.append((registry_key, alias_norm, len(alias_norm.split()), is_exact_phrase))

        # Sort by: exact phrase first, then length (longer first), then key
        candidates.sort(key=lambda x: (-x[3], -x[2], x[0]))

        # Exact substring matches (prefer longer/more specific)
        for registry_key, alias_norm, _, is_exact_phrase in candidates:
            if alias_norm in normalized:
                # For single-word matches, be more careful with generic words
                if len(alias_norm.split()) == 1 and len(normalized.split()) == 1:
                    generic_words = {"laser", "brow", "brows", "lash", "lashes", "facial", "pmu", "exfoliate"}
                    if alias_norm not in generic_words:
                        return registry_key
                else:
                    return registry_key

        # Token-based contains (check if all words in alias are in text)
        for registry_key, alias_norm, _, _ in candidates:
            alias_words = set(alias_norm.split())
            text_words = set(normalized.split())
            if alias_words.issubset(text_words) and len(alias_words) > 0:
                return registry_key

        # Fuzzy matches with threshold
        for registry_key, alias_norm, _, _ in candidates:
            if _fuzzy_match(alias_norm, normalized, threshold=0.85):
                return registry_key

        return None

    def is_ambiguous_category_question(self, text: str) -> str | None:
        """
        Detect ambiguous category questions that need clarification.
        Returns the category name if ambiguous, None otherwise.
        """
        normalized = _normalize_text(text)

        ambiguous_patterns = {
            "laser": "laser",
            "depilacion laser": "laser",
            "depilación láser": "laser",
            "laser hair removal": "laser",
        }

        specific_indicators = [
            "full body", "face", "arm", "leg", "brazilian", "bikini",
            "jawline", "upper lip", "forehead", "cheek", "chin", "neck",
            "nose", "sideburn", "men", "man", "women", "woman",
            "lower leg", "lower arm", "chest", "abdomen", "back", "underarm",
            "upper body", "lower body"
        ]

        for pattern, category in ambiguous_patterns.items():
            if pattern in normalized:
                if not any(indicator in normalized for indicator in specific_indicators):
                    return category

        return None

    def get_service_display_name(self, service: str) -> str:
        key = service.strip().lower()
        return self._display_names.get(key, service)


def _normalize_text(text: str) -> str:
    normalized = text.lower().replace("+", " ")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _fuzzy_match(alias: str, text: str, threshold: float = 0.88) -> bool:
    alias_words = alias.split()
    text_words = text.split()
    if not alias_words or not text_words:
        return False

    window = len(alias_words)
    if len(text_words) < window:
        return SequenceMatcher(None, alias, text).ratio() >= threshold

    for i in range(len(text_words) - window + 1):
        chunk = " ".join(text_words[i : i + window])
        if SequenceMatcher(None, alias, chunk).ratio() >= threshold:
            return True
    return False


def build_kb() -> StructuredKnowledgeBase:
    facial_en = (
        "LIMITED TIME PROMO\n\n"
        "Facial + Deep Blackhead Removal\n"
        "Pricing: $120–$150\n\n"
        "Deep cleansing\n"
        "Blackhead removal\n"
        "Gentle exfoliation\n"
        "Calming mask\n"
        "Ultrasonic Skin Treatment\n"
        "Hydration + SPF finish\n\n"
        "This treatment is customized based on your skin to ensure the best results possible."
    )

    facial_es = (
        "LIMITED TIME PROMO\n\n"
        "Facial + Deep Blackhead Removal\n"
        "Precio: $120–$150\n\n"
        "Limpieza profunda\n"
        "Extraccion de puntos negros\n"
        "Exfoliacion suave\n"
        "Mascarilla calmante\n"
        "Ultrasonic Skin Treatment\n"
        "Hidratacion + SPF\n\n"
        "Este tratamiento se personaliza segun tu piel para lograr los mejores resultados posibles."
    )

    laser_en = (
        "Laser Hair Removal\n"
        "Pricing: $150, full body diode laser\n"
        "Add-on: Full face, $50, with full body\n"
        "Recommended: about 6 sessions\n"
        "Promo: price stays if sessions are consecutive\n"
        "Brazilian available, please confirm full body or Brazilian only"
    )

    laser_es = (
        "Depilación Láser\n"
        "Precio: $150, cuerpo completo con diodo\n"
        "Extra: rostro completo, $50, con cuerpo completo\n"
        "Recomendado: aproximadamente 6 sesiones\n"
        "Promo: el precio se mantiene si las sesiones son consecutivas\n"
        "Brazilian disponible, confirma si es cuerpo completo o solo Brazilian"
    )

    lash_promo_en = (
        "LASH LAMINATION PROMO\n\n"
        "Lash Combo\n"
        "Pricing: $85\n\n"
        "Includes:\n"
        "Lash Lamination\n"
        "Tinting\n\n"
        "Bonus: Complimentary aftercare gift"
    )

    lash_promo_es = (
        "LASH LAMINATION PROMO\n\n"
        "Lash Combo\n"
        "Precio: $85\n\n"
        "Incluye:\n"
        "Lash Lamination\n"
        "Tinting\n\n"
        "Bonus: Complimentary aftercare gift"
    )

    brow_en = (
        "Eyebrow Shaping + Lamination + Tinting\n\n"
        "Includes:\n"
        "Shaping\n"
        "Lamination\n"
        "Tinting"
    )

    brow_es = (
        "Eyebrow Shaping + Lamination + Tinting\n\n"
        "Incluye:\n"
        "Shaping\n"
        "Lamination\n"
        "Tinting"
    )

    services_en = (
        "Here is a list of the services we offer\n\n"
        "✨Laser Hair Removal\n"
        "✨Eyelash Lamination + Tinting\n"
        "✨Permanent Makeup\n"
        "✨Facial + Deep Blackhead Removal\n"
        "✨Eyebrow Shaping + Lamination + Tinting"
    )

    services_es = (
        "Aquí está la lista de servicios que ofrecemos\n\n"
        "✨Depilación Láser\n"
        "✨Laminación + Tinte de Pestañas\n"
        "✨Maquillaje Permanente\n"
        "✨Facial + Extracción Profunda de Puntos Negros\n"
        "✨Diseño + Laminación + Tinte de Cejas"
    )

    location_en = (
        "We are located at:\n"
        "📍 375 N First St, Burbank, CA 91502"
    )

    location_es = (
        "Estamos ubicados en:\n"
        "📍 375 N First St, Burbank, CA 91502"
    )

    hours_en = "Hours: Monday to Sunday, 10:00 AM to 7:00 PM."
    hours_es = "Horario: Lunes a Domingo, 10:00 AM a 7:00 PM."

    equipment_en = (
        "Laser machine: DM40P Non Crystal Diode Laser. "
        "Wavelengths: 755 nm, 808 nm, 940 nm, 1064 nm. "
        "Safe for all skin types. Advanced cooling. Virtually pain-free."
    )

    equipment_es = (
        "Laser machine: DM40P Non Crystal Diode Laser. "
        "Wavelengths: 755 nm, 808 nm, 940 nm, 1064 nm. "
        "Safe for all skin types. Advanced cooling. Virtually pain-free."
    )

    eligibility_en = "If using Tretinoin, stop 5 to 7 days before treatment."
    eligibility_es = "Si usas Tretinoin, debes suspenderlo 5 a 7 dias antes del tratamiento."

    booking_en = "Please share your preferred day and time to check availability."
    booking_es = "Por favor comparte tu dia y hora preferidos para revisar disponibilidad."

    booking_info_en = "Happy to help with booking."
    booking_info_es = "Con gusto ayudamos con la cita."

    brazilian_en = "Brazilian supported (please confirm if full body or Brazilian only)."
    brazilian_es = "Brazilian disponible (por favor confirma si es full body o solo Brazilian)."

    laser_clarification_en = (
        "Laser Hair Removal pricing depends on the area.\n\n"
        "We offer:\n"
        "• Full Body\n"
        "• Face\n"
        "• Arms\n"
        "• Legs\n"
        "• Brazilian\n"
        "• Men's Laser Services"
    )

    laser_clarification_es = (
        "El precio de Depilación Láser depende del área.\n\n"
        "Ofrecemos:\n"
        "• Full Body\n"
        "• Face\n"
        "• Arms\n"
        "• Legs\n"
        "• Brazilian\n"
        "• Men's Laser Services"
    )

    full_body_diode_laser_en = "Full Body Diode Laser\nPricing: $150"
    full_body_diode_laser_es = "Full Body Diode Laser\nPrecio: $150"

    full_face_laser_en = "Full Face Laser\nPricing: $50\n\nAdd-on with Full Body only."
    full_face_laser_es = "Full Face Laser\nPrecio: $50\n\nAgregado solo con Full Body."

    full_legs_en = "Full Legs\nPricing: $60"
    full_legs_es = "Full Legs\nPrecio: $60"

    lower_legs_en = "Lower Legs\nPricing: $35"
    lower_legs_es = "Lower Legs\nPrecio: $35"

    full_arms_en = "Full Arms\nPricing: $50"
    full_arms_es = "Full Arms\nPrecio: $50"

    lower_arms_en = "Lower Arms\nPricing: $30"
    lower_arms_es = "Lower Arms\nPrecio: $30"

    chest_en = "Chest\nPricing: $30"
    chest_es = "Chest\nPrecio: $30"

    abdomen_en = "Abdomen\nPricing: $30"
    abdomen_es = "Abdomen\nPrecio: $30"

    brazilian_bikini_en = "Brazilian (Bikini)\nPricing: $65"
    brazilian_bikini_es = "Brazilian (Bikini)\nPrecio: $65"

    back_en = "Back\nPricing: $45"
    back_es = "Back\nPrecio: $45"

    underarms_en = "Underarms\nPricing: $45"
    underarms_es = "Underarms\nPrecio: $45"

    upper_lip_en = "Upper Lip\nPricing: $30"
    upper_lip_es = "Upper Lip\nPrecio: $30"

    forehead_en = "Forehead\nPricing: $40"
    forehead_es = "Forehead\nPrecio: $40"

    sideburns_cheeks_en = "Sideburns / Cheeks\nPricing: $40"
    sideburns_cheeks_es = "Sideburns / Cheeks\nPrecio: $40"

    chin_en = "Chin\nPricing: $30"
    chin_es = "Chin\nPrecio: $30"

    neck_en = "Neck\nPricing: $45"
    neck_es = "Neck\nPrecio: $45"

    jawline_en = "Jawline\nPricing: $30"
    jawline_es = "Jawline\nPrecio: $30"

    nose_diode_laser_en = "Nose (Diode Laser)\nPricing: $40"
    nose_diode_laser_es = "Nose (Diode Laser)\nPrecio: $40"

    full_upper_body_diode_laser_men_en = "Full Upper Body Diode Laser (Men)\nPricing: $250"
    full_upper_body_diode_laser_men_es = "Full Upper Body Diode Laser (Men)\nPrecio: $250"

    full_face_laser_men_en = "Full Face Laser (Men)\nPricing: $80"
    full_face_laser_men_es = "Full Face Laser (Men)\nPrecio: $80"

    upper_body_one_part_men_en = "Upper Body – One Part (Men)\nPricing: $90"
    upper_body_one_part_men_es = "Upper Body – One Part (Men)\nPrecio: $90"

    facelift_massage_en = "Facelift Massage\nPricing: $90"
    facelift_massage_es = "Facelift Massage\nPrecio: $90"

    microdermabrasion_en = "Microdermabrasion\nPricing: $180"
    microdermabrasion_es = "Microdermabrasion\nPrecio: $180"

    lash_extensions_all_shapes_en = "Lash Extensions (All Shapes)\nPricing: $120"
    lash_extensions_all_shapes_es = "Lash Extensions (All Shapes)\nPrecio: $120"

    eyebrow_lamination_tint_shaping_en = "Eyebrow Lamination + Tint + Shaping\nPricing: $110"
    eyebrow_lamination_tint_shaping_es = "Eyebrow Lamination + Tint + Shaping\nPrecio: $110"

    eyebrow_lamination_en = "Eyebrow Lamination\nPricing: $85"
    eyebrow_lamination_es = "Eyebrow Lamination\nPrecio: $85"

    eyebrow_tinting_en = "Eyebrow Tinting\nPricing: $85"
    eyebrow_tinting_es = "Eyebrow Tinting\nPrecio: $85"

    eyebrow_shaping_en = "Eyebrow Shaping\nPricing: $85"
    eyebrow_shaping_es = "Eyebrow Shaping\nPrecio: $85"

    facial_blackhead_removal_lash_lamination_en = "Facial (Blackhead Removal) + Lash Lamination\nPricing: $155"
    facial_blackhead_removal_lash_lamination_es = "Facial (Blackhead Removal) + Lash Lamination\nPrecio: $155"

    lash_lamination_eyebrow_lamination_en = "Lash Lamination + Eyebrow Lamination\nPricing: $150"
    lash_lamination_eyebrow_lamination_es = "Lash Lamination + Eyebrow Lamination\nPrecio: $150"

    facial_blackhead_removal_laser_en = "Facial (Blackhead Removal) + Laser\nPricing: $200"
    facial_blackhead_removal_laser_es = "Facial (Blackhead Removal) + Laser\nPrecio: $200"

    facial_blackhead_removal_eyebrow_lamination_en = "Facial (Blackhead Removal) + Eyebrow Lamination\nPricing: $175"
    facial_blackhead_removal_eyebrow_lamination_es = "Facial (Blackhead Removal) + Eyebrow Lamination\nPrecio: $175"

    pmu_lips_en = "PMU – Lips\nPricing: $300"
    pmu_lips_es = "PMU – Lips\nPrecio: $300"

    pmu_eyebrows_en = "PMU – Eyebrows\nPricing: $350"
    pmu_eyebrows_es = "PMU – Eyebrows\nPrecio: $350"

    pmu_eyeliner_en = "PMU – Eyeliner\nPricing: $250"
    pmu_eyeliner_es = "PMU – Eyeliner\nPrecio: $250"

    lip_pmu_touchup_en = "Lip PMU Touch-up\nPricing: $200"
    lip_pmu_touchup_es = "Lip PMU Touch-up\nPrecio: $200"

    deposit_hold_en = "Deposit Hold\nPricing: $20"
    deposit_hold_es = "Deposit Hold\nPrecio: $20"

    data: dict[str, dict[str, dict[str, ResponseTemplate]]] = {
        "services_list": {
            "_default": {
                "en": ResponseTemplate(services_en, ["Laser Hair Removal"]),
                "es": ResponseTemplate(services_es, ["Laser Hair Removal"]),
            }
        },
        "pricing": {
            "facial + deep blackhead removal": {
                "en": ResponseTemplate(facial_en, ["LIMITED TIME PROMO", "$120–$150"]),
                "es": ResponseTemplate(facial_es, ["LIMITED TIME PROMO", "$120–$150"]),
            },
            "laser hair removal": {
                "en": ResponseTemplate(laser_en, ["$150", "Add full face: $50"]),
                "es": ResponseTemplate(laser_es, ["$150", "Add full face: $50"]),
            },
            "eyelash lamination + tinting": {
                "en": ResponseTemplate(lash_promo_en, ["LASH LAMINATION PROMO", "$85"]),
                "es": ResponseTemplate(lash_promo_es, ["LASH LAMINATION PROMO", "$85"]),
            },
            "eyebrow shaping + lamination + tinting": {
                "en": ResponseTemplate(brow_en, ["Eyebrow Shaping + Lamination + Tinting"]),
                "es": ResponseTemplate(brow_es, ["Eyebrow Shaping + Lamination + Tinting"]),
            },
            "full body diode laser": {
                "en": ResponseTemplate(full_body_diode_laser_en, ["$150"]),
                "es": ResponseTemplate(full_body_diode_laser_es, ["$150"]),
            },
            "full face laser": {
                "en": ResponseTemplate(full_face_laser_en, ["$50"]),
                "es": ResponseTemplate(full_face_laser_es, ["$50"]),
            },
            "full legs": {
                "en": ResponseTemplate(full_legs_en, ["$60"]),
                "es": ResponseTemplate(full_legs_es, ["$60"]),
            },
            "lower legs": {
                "en": ResponseTemplate(lower_legs_en, ["$35"]),
                "es": ResponseTemplate(lower_legs_es, ["$35"]),
            },
            "full arms": {
                "en": ResponseTemplate(full_arms_en, ["$50"]),
                "es": ResponseTemplate(full_arms_es, ["$50"]),
            },
            "lower arms": {
                "en": ResponseTemplate(lower_arms_en, ["$30"]),
                "es": ResponseTemplate(lower_arms_es, ["$30"]),
            },
            "chest": {
                "en": ResponseTemplate(chest_en, ["$30"]),
                "es": ResponseTemplate(chest_es, ["$30"]),
            },
            "abdomen": {
                "en": ResponseTemplate(abdomen_en, ["$30"]),
                "es": ResponseTemplate(abdomen_es, ["$30"]),
            },
            "brazilian bikini": {
                "en": ResponseTemplate(brazilian_bikini_en, ["$65"]),
                "es": ResponseTemplate(brazilian_bikini_es, ["$65"]),
            },
            "back": {
                "en": ResponseTemplate(back_en, ["$45"]),
                "es": ResponseTemplate(back_es, ["$45"]),
            },
            "underarms": {
                "en": ResponseTemplate(underarms_en, ["$45"]),
                "es": ResponseTemplate(underarms_es, ["$45"]),
            },
            "upper lip": {
                "en": ResponseTemplate(upper_lip_en, ["$30"]),
                "es": ResponseTemplate(upper_lip_es, ["$30"]),
            },
            "forehead": {
                "en": ResponseTemplate(forehead_en, ["$40"]),
                "es": ResponseTemplate(forehead_es, ["$40"]),
            },
            "sideburns cheeks": {
                "en": ResponseTemplate(sideburns_cheeks_en, ["$40"]),
                "es": ResponseTemplate(sideburns_cheeks_es, ["$40"]),
            },
            "chin": {
                "en": ResponseTemplate(chin_en, ["$30"]),
                "es": ResponseTemplate(chin_es, ["$30"]),
            },
            "neck": {
                "en": ResponseTemplate(neck_en, ["$45"]),
                "es": ResponseTemplate(neck_es, ["$45"]),
            },
            "jawline": {
                "en": ResponseTemplate(jawline_en, ["$30"]),
                "es": ResponseTemplate(jawline_es, ["$30"]),
            },
            "nose diode laser": {
                "en": ResponseTemplate(nose_diode_laser_en, ["$40"]),
                "es": ResponseTemplate(nose_diode_laser_es, ["$40"]),
            },
            "full upper body diode laser men": {
                "en": ResponseTemplate(full_upper_body_diode_laser_men_en, ["$250"]),
                "es": ResponseTemplate(full_upper_body_diode_laser_men_es, ["$250"]),
            },
            "full face laser men": {
                "en": ResponseTemplate(full_face_laser_men_en, ["$80"]),
                "es": ResponseTemplate(full_face_laser_men_es, ["$80"]),
            },
            "upper body one part men": {
                "en": ResponseTemplate(upper_body_one_part_men_en, ["$90"]),
                "es": ResponseTemplate(upper_body_one_part_men_es, ["$90"]),
            },
            "facelift massage": {
                "en": ResponseTemplate(facelift_massage_en, ["$90"]),
                "es": ResponseTemplate(facelift_massage_es, ["$90"]),
            },
            "microdermabrasion": {
                "en": ResponseTemplate(microdermabrasion_en, ["$180"]),
                "es": ResponseTemplate(microdermabrasion_es, ["$180"]),
            },
            "lash extensions all shapes": {
                "en": ResponseTemplate(lash_extensions_all_shapes_en, ["$120"]),
                "es": ResponseTemplate(lash_extensions_all_shapes_es, ["$120"]),
            },
            "eyebrow lamination tint shaping": {
                "en": ResponseTemplate(eyebrow_lamination_tint_shaping_en, ["$110"]),
                "es": ResponseTemplate(eyebrow_lamination_tint_shaping_es, ["$110"]),
            },
            "eyebrow lamination": {
                "en": ResponseTemplate(eyebrow_lamination_en, ["$85"]),
                "es": ResponseTemplate(eyebrow_lamination_es, ["$85"]),
            },
            "eyebrow tinting": {
                "en": ResponseTemplate(eyebrow_tinting_en, ["$85"]),
                "es": ResponseTemplate(eyebrow_tinting_es, ["$85"]),
            },
            "eyebrow shaping": {
                "en": ResponseTemplate(eyebrow_shaping_en, ["$85"]),
                "es": ResponseTemplate(eyebrow_shaping_es, ["$85"]),
            },
            "facial blackhead removal lash lamination": {
                "en": ResponseTemplate(facial_blackhead_removal_lash_lamination_en, ["$155"]),
                "es": ResponseTemplate(facial_blackhead_removal_lash_lamination_es, ["$155"]),
            },
            "lash lamination eyebrow lamination": {
                "en": ResponseTemplate(lash_lamination_eyebrow_lamination_en, ["$150"]),
                "es": ResponseTemplate(lash_lamination_eyebrow_lamination_es, ["$150"]),
            },
            "facial blackhead removal laser": {
                "en": ResponseTemplate(facial_blackhead_removal_laser_en, ["$200"]),
                "es": ResponseTemplate(facial_blackhead_removal_laser_es, ["$200"]),
            },
            "facial blackhead removal eyebrow lamination": {
                "en": ResponseTemplate(facial_blackhead_removal_eyebrow_lamination_en, ["$175"]),
                "es": ResponseTemplate(facial_blackhead_removal_eyebrow_lamination_es, ["$175"]),
            },
            "pmu lips": {
                "en": ResponseTemplate(pmu_lips_en, ["$300"]),
                "es": ResponseTemplate(pmu_lips_es, ["$300"]),
            },
            "pmu eyebrows": {
                "en": ResponseTemplate(pmu_eyebrows_en, ["$350"]),
                "es": ResponseTemplate(pmu_eyebrows_es, ["$350"]),
            },
            "pmu eyeliner": {
                "en": ResponseTemplate(pmu_eyeliner_en, ["$250"]),
                "es": ResponseTemplate(pmu_eyeliner_es, ["$250"]),
            },
            "lip pmu touchup": {
                "en": ResponseTemplate(lip_pmu_touchup_en, ["$200"]),
                "es": ResponseTemplate(lip_pmu_touchup_es, ["$200"]),
            },
            "deposit hold": {
                "en": ResponseTemplate(deposit_hold_en, ["$20"]),
                "es": ResponseTemplate(deposit_hold_es, ["$20"]),
            },
        },
        "promo_pricing": {
            "_default": {
                "en": ResponseTemplate(lash_promo_en, ["LASH LAMINATION PROMO", "$85"]),
                "es": ResponseTemplate(lash_promo_es, ["LASH LAMINATION PROMO", "$85"]),
            }
        },
        "service_details": {
            "facial + deep blackhead removal": {
                "en": ResponseTemplate(facial_en, ["LIMITED TIME PROMO", "$120–$150"]),
                "es": ResponseTemplate(facial_es, ["LIMITED TIME PROMO", "$120–$150"]),
            },
            "laser hair removal": {
                "en": ResponseTemplate(laser_en, ["$150", "Add full face: $50"]),
                "es": ResponseTemplate(laser_es, ["$150", "Add full face: $50"]),
            },
            "eyelash lamination + tinting": {
                "en": ResponseTemplate(lash_promo_en, ["LASH LAMINATION PROMO", "$85"]),
                "es": ResponseTemplate(lash_promo_es, ["LASH LAMINATION PROMO", "$85"]),
            },
            "eyebrow shaping + lamination + tinting": {
                "en": ResponseTemplate(brow_en, ["Eyebrow Shaping + Lamination + Tinting"]),
                "es": ResponseTemplate(brow_es, ["Eyebrow Shaping + Lamination + Tinting"]),
            },
            "full body diode laser": {
                "en": ResponseTemplate(full_body_diode_laser_en, ["$150"]),
                "es": ResponseTemplate(full_body_diode_laser_es, ["$150"]),
            },
            "full face laser": {
                "en": ResponseTemplate(full_face_laser_en, ["$50"]),
                "es": ResponseTemplate(full_face_laser_es, ["$50"]),
            },
            "full legs": {
                "en": ResponseTemplate(full_legs_en, ["$60"]),
                "es": ResponseTemplate(full_legs_es, ["$60"]),
            },
            "lower legs": {
                "en": ResponseTemplate(lower_legs_en, ["$35"]),
                "es": ResponseTemplate(lower_legs_es, ["$35"]),
            },
            "full arms": {
                "en": ResponseTemplate(full_arms_en, ["$50"]),
                "es": ResponseTemplate(full_arms_es, ["$50"]),
            },
            "lower arms": {
                "en": ResponseTemplate(lower_arms_en, ["$30"]),
                "es": ResponseTemplate(lower_arms_es, ["$30"]),
            },
            "chest": {
                "en": ResponseTemplate(chest_en, ["$30"]),
                "es": ResponseTemplate(chest_es, ["$30"]),
            },
            "abdomen": {
                "en": ResponseTemplate(abdomen_en, ["$30"]),
                "es": ResponseTemplate(abdomen_es, ["$30"]),
            },
            "brazilian bikini": {
                "en": ResponseTemplate(brazilian_bikini_en, ["$65"]),
                "es": ResponseTemplate(brazilian_bikini_es, ["$65"]),
            },
            "back": {
                "en": ResponseTemplate(back_en, ["$45"]),
                "es": ResponseTemplate(back_es, ["$45"]),
            },
            "underarms": {
                "en": ResponseTemplate(underarms_en, ["$45"]),
                "es": ResponseTemplate(underarms_es, ["$45"]),
            },
            "upper lip": {
                "en": ResponseTemplate(upper_lip_en, ["$30"]),
                "es": ResponseTemplate(upper_lip_es, ["$30"]),
            },
            "forehead": {
                "en": ResponseTemplate(forehead_en, ["$40"]),
                "es": ResponseTemplate(forehead_es, ["$40"]),
            },
            "sideburns cheeks": {
                "en": ResponseTemplate(sideburns_cheeks_en, ["$40"]),
                "es": ResponseTemplate(sideburns_cheeks_es, ["$40"]),
            },
            "chin": {
                "en": ResponseTemplate(chin_en, ["$30"]),
                "es": ResponseTemplate(chin_es, ["$30"]),
            },
            "neck": {
                "en": ResponseTemplate(neck_en, ["$45"]),
                "es": ResponseTemplate(neck_es, ["$45"]),
            },
            "jawline": {
                "en": ResponseTemplate(jawline_en, ["$30"]),
                "es": ResponseTemplate(jawline_es, ["$30"]),
            },
            "nose diode laser": {
                "en": ResponseTemplate(nose_diode_laser_en, ["$40"]),
                "es": ResponseTemplate(nose_diode_laser_es, ["$40"]),
            },
            "full upper body diode laser men": {
                "en": ResponseTemplate(full_upper_body_diode_laser_men_en, ["$250"]),
                "es": ResponseTemplate(full_upper_body_diode_laser_men_es, ["$250"]),
            },
            "full face laser men": {
                "en": ResponseTemplate(full_face_laser_men_en, ["$80"]),
                "es": ResponseTemplate(full_face_laser_men_es, ["$80"]),
            },
            "upper body one part men": {
                "en": ResponseTemplate(upper_body_one_part_men_en, ["$90"]),
                "es": ResponseTemplate(upper_body_one_part_men_es, ["$90"]),
            },
            "facelift massage": {
                "en": ResponseTemplate(facelift_massage_en, ["$90"]),
                "es": ResponseTemplate(facelift_massage_es, ["$90"]),
            },
            "microdermabrasion": {
                "en": ResponseTemplate(microdermabrasion_en, ["$180"]),
                "es": ResponseTemplate(microdermabrasion_es, ["$180"]),
            },
            "lash extensions all shapes": {
                "en": ResponseTemplate(lash_extensions_all_shapes_en, ["$120"]),
                "es": ResponseTemplate(lash_extensions_all_shapes_es, ["$120"]),
            },
            "eyebrow lamination tint shaping": {
                "en": ResponseTemplate(eyebrow_lamination_tint_shaping_en, ["$110"]),
                "es": ResponseTemplate(eyebrow_lamination_tint_shaping_es, ["$110"]),
            },
            "eyebrow lamination": {
                "en": ResponseTemplate(eyebrow_lamination_en, ["$85"]),
                "es": ResponseTemplate(eyebrow_lamination_es, ["$85"]),
            },
            "eyebrow tinting": {
                "en": ResponseTemplate(eyebrow_tinting_en, ["$85"]),
                "es": ResponseTemplate(eyebrow_tinting_es, ["$85"]),
            },
            "eyebrow shaping": {
                "en": ResponseTemplate(eyebrow_shaping_en, ["$85"]),
                "es": ResponseTemplate(eyebrow_shaping_es, ["$85"]),
            },
            "facial blackhead removal lash lamination": {
                "en": ResponseTemplate(facial_blackhead_removal_lash_lamination_en, ["$155"]),
                "es": ResponseTemplate(facial_blackhead_removal_lash_lamination_es, ["$155"]),
            },
            "lash lamination eyebrow lamination": {
                "en": ResponseTemplate(lash_lamination_eyebrow_lamination_en, ["$150"]),
                "es": ResponseTemplate(lash_lamination_eyebrow_lamination_es, ["$150"]),
            },
            "facial blackhead removal laser": {
                "en": ResponseTemplate(facial_blackhead_removal_laser_en, ["$200"]),
                "es": ResponseTemplate(facial_blackhead_removal_laser_es, ["$200"]),
            },
            "facial blackhead removal eyebrow lamination": {
                "en": ResponseTemplate(facial_blackhead_removal_eyebrow_lamination_en, ["$175"]),
                "es": ResponseTemplate(facial_blackhead_removal_eyebrow_lamination_es, ["$175"]),
            },
            "pmu lips": {
                "en": ResponseTemplate(pmu_lips_en, ["$300"]),
                "es": ResponseTemplate(pmu_lips_es, ["$300"]),
            },
            "pmu eyebrows": {
                "en": ResponseTemplate(pmu_eyebrows_en, ["$350"]),
                "es": ResponseTemplate(pmu_eyebrows_es, ["$350"]),
            },
            "pmu eyeliner": {
                "en": ResponseTemplate(pmu_eyeliner_en, ["$250"]),
                "es": ResponseTemplate(pmu_eyeliner_es, ["$250"]),
            },
            "lip pmu touchup": {
                "en": ResponseTemplate(lip_pmu_touchup_en, ["$200"]),
                "es": ResponseTemplate(lip_pmu_touchup_es, ["$200"]),
            },
            "deposit hold": {
                "en": ResponseTemplate(deposit_hold_en, ["$20"]),
                "es": ResponseTemplate(deposit_hold_es, ["$20"]),
            },
        },
        "location": {
            "_default": {
                "en": ResponseTemplate(location_en, ["375 N First St"]),
                "es": ResponseTemplate(location_es, ["375 N First St"]),
            }
        },
        "hours": {
            "_default": {
                "en": ResponseTemplate(hours_en, ["10:00 AM to 7:00 PM"]),
                "es": ResponseTemplate(hours_es, ["10:00 AM a 7:00 PM"]),
            }
        },
        "availability": {
            "_default": {
                "en": ResponseTemplate(booking_en, ["preferred day and time"]),
                "es": ResponseTemplate(booking_es, ["dia y hora"]),
            }
        },
        "booking": {
            "_default": {
                "en": ResponseTemplate(booking_en, ["preferred day and time"]),
                "es": ResponseTemplate(booking_es, ["dia y hora"]),
            }
        },
        "equipment": {
            "_default": {
                "en": ResponseTemplate(equipment_en, ["DM40P"]),
                "es": ResponseTemplate(equipment_es, ["DM40P"]),
            }
        },
        "eligibility": {
            "_default": {
                "en": ResponseTemplate(eligibility_en, ["Tretinoin"]),
                "es": ResponseTemplate(eligibility_es, ["Tretinoin"]),
            }
        },
        "closing": {
            "_default": {
                "en": ResponseTemplate(booking_en, ["preferred day and time"]),
                "es": ResponseTemplate(booking_es, ["dia y hora"]),
            }
        },
        "booking_info": {
            "_default": {
                "en": ResponseTemplate(booking_info_en, ["Happy to help with booking."]),
                "es": ResponseTemplate(booking_info_es, ["Con gusto ayudamos con la cita."]),
            }
        },
        "brazilian_clarification": {
            "laser hair removal": {
                "en": ResponseTemplate(brazilian_en, ["Brazilian supported"]),
                "es": ResponseTemplate(brazilian_es, ["Brazilian"]),
            }
        },
        "laser_clarification": {
            "_default": {
                "en": ResponseTemplate(laser_clarification_en, ["Laser Hair Removal"]),
                "es": ResponseTemplate(laser_clarification_es, ["Depilación Láser"]),
            }
        },
    }

    aliases = {
        "facial + deep blackhead removal": [
            "facial",
            "blackhead",
            "black head",
            "blackhead removal",
            "black head removal",
            "deep blackhead removal",
            "facial deep blackhead",
            "facial blackhead",
            "facial + blackhead removal",
        ],
        "laser hair removal": [
            "laser",
            "laser hair",
            "laser hair removal",
            "full body",
            "brazilian",
        ],
        "eyelash lamination + tinting": [
            "lash",
            "lashes",
            "lash lamination",
            "lamination",
            "eyelash lamination",
            "lash combo",
        ],
        "eyebrow shaping + lamination + tinting": [
            "brow",
            "brows",
            "eyebrow",
            "eyebrow shaping",
            "brow lamination",
        ],
        "full body diode laser": [
            "full body diode laser",
            "full body laser",
            "diode full body",
            "full body diode",
            "full body",
        ],
        "full face laser": [
            "full face laser",
            "full face",
            "face laser",
        ],
        "full legs": [
            "full legs",
            "legs",
        ],
        "lower legs": [
            "lower legs",
            "lower leg",
        ],
        "full arms": [
            "full arms",
            "arms",
        ],
        "lower arms": [
            "lower arms",
            "lower arm",
        ],
        "chest": [
            "chest",
        ],
        "abdomen": [
            "abdomen",
            "stomach",
            "belly",
        ],
        "brazilian bikini": [
            "brazilian bikini",
            "brazilian",
            "bikini",
            "brazilian laser",
            "bikini laser",
        ],
        "back": [
            "back",
        ],
        "underarms": [
            "underarms",
            "underarm",
            "armpits",
            "armpit",
        ],
        "upper lip": [
            "upper lip",
            "lip",
            "upper lip laser",
        ],
        "forehead": [
            "forehead",
        ],
        "sideburns cheeks": [
            "sideburns cheeks",
            "sideburns",
            "cheeks",
            "cheek",
            "sideburn",
        ],
        "chin": [
            "chin",
        ],
        "neck": [
            "neck",
        ],
        "jawline": [
            "jawline",
            "jaw line",
            "jaw",
        ],
        "nose diode laser": [
            "nose diode laser",
            "nose laser",
            "nose",
        ],
        "full upper body diode laser men": [
            "full upper body diode laser men",
            "full upper body men",
            "upper body men",
            "men full upper body",
            "men upper body",
        ],
        "full face laser men": [
            "full face laser men",
            "full face men",
            "men full face",
            "men face laser",
        ],
        "upper body one part men": [
            "upper body one part men",
            "one part men",
            "men one part",
        ],
        "facelift massage": [
            "facelift massage",
            "facelift",
            "face lift massage",
        ],
        "microdermabrasion": [
            "microdermabrasion",
            "microderm",
            "micro dermabrasion",
        ],
        "lash extensions all shapes": [
            "lash extensions all shapes",
            "lash extensions",
            "lash extension",
            "extensions",
            "extension",
        ],
        "eyebrow lamination tint shaping": [
            "eyebrow lamination tint shaping",
            "eyebrow lamination tint",
            "brow lamination tint shaping",
            "brow lamination tint",
        ],
        "eyebrow lamination": [
            "eyebrow lamination",
            "brow lamination",
            "eyebrow lash",
        ],
        "eyebrow tinting": [
            "eyebrow tinting",
            "eyebrow tint",
            "brow tinting",
            "brow tint",
            "eyebrow dye",
            "brow dye",
        ],
        "eyebrow shaping": [
            "eyebrow shaping",
            "brow shaping",
            "eyebrow shape",
            "brow shape",
        ],
        "facial blackhead removal lash lamination": [
            "facial blackhead removal lash lamination",
            "facial and lash lamination",
            "facial lash lamination",
            "facial lash",
            "facial + lash lamination",
            "facial + lash",
        ],
        "lash lamination eyebrow lamination": [
            "lash lamination eyebrow lamination",
            "lash eyebrow lamination",
            "lash brow lamination",
        ],
        "facial blackhead removal laser": [
            "facial blackhead removal laser",
            "facial laser",
        ],
        "facial blackhead removal eyebrow lamination": [
            "facial blackhead removal eyebrow lamination",
            "facial eyebrow lamination",
            "facial brow lamination",
        ],
        "pmu lips": [
            "pmu lips",
            "lip pmu",
            "pmu lip",
            "permanent makeup lips",
            "permanent lip",
            "lip permanent makeup",
        ],
        "pmu eyebrows": [
            "pmu eyebrows",
            "pmu eyebrow",
            "pmu brows",
            "pmu brow",
            "permanent makeup eyebrows",
            "permanent eyebrow",
            "eyebrow permanent makeup",
        ],
        "pmu eyeliner": [
            "pmu eyeliner",
            "pmu liner",
            "permanent makeup eyeliner",
            "permanent eyeliner",
            "eyeliner permanent makeup",
        ],
        "lip pmu touchup": [
            "lip pmu touchup",
            "lip pmu touch up",
            "lip touchup",
            "lip touch up",
            "pmu lip touchup",
        ],
        "deposit hold": [
            "deposit hold",
            "deposit",
            "hold",
        ],
    }

    display_names = {
        "facial + deep blackhead removal": "Facial + Deep Blackhead Removal",
        "laser hair removal": "Laser Hair Removal",
        "eyelash lamination + tinting": "Eyelash Lamination + Tinting",
        "eyebrow shaping + lamination + tinting": "Eyebrow Shaping + Lamination + Tinting",
        "full body diode laser": "Full Body Diode Laser",
        "full face laser": "Full Face Laser",
        "full legs": "Full Legs",
        "lower legs": "Lower Legs",
        "full arms": "Full Arms",
        "lower arms": "Lower Arms",
        "chest": "Chest",
        "abdomen": "Abdomen",
        "brazilian bikini": "Brazilian (Bikini)",
        "back": "Back",
        "underarms": "Underarms",
        "upper lip": "Upper Lip",
        "forehead": "Forehead",
        "sideburns cheeks": "Sideburns / Cheeks",
        "chin": "Chin",
        "neck": "Neck",
        "jawline": "Jawline",
        "nose diode laser": "Nose (Diode Laser)",
        "full upper body diode laser men": "Full Upper Body Diode Laser (Men)",
        "full face laser men": "Full Face Laser (Men)",
        "upper body one part men": "Upper Body – One Part (Men)",
        "facelift massage": "Facelift Massage",
        "microdermabrasion": "Microdermabrasion",
        "lash extensions all shapes": "Lash Extensions (All Shapes)",
        "eyebrow lamination tint shaping": "Eyebrow Lamination + Tint + Shaping",
        "eyebrow lamination": "Eyebrow Lamination",
        "eyebrow tinting": "Eyebrow Tinting",
        "eyebrow shaping": "Eyebrow Shaping",
        "facial blackhead removal lash lamination": "Facial (Blackhead Removal) + Lash Lamination",
        "lash lamination eyebrow lamination": "Lash Lamination + Eyebrow Lamination",
        "facial blackhead removal laser": "Facial (Blackhead Removal) + Laser",
        "facial blackhead removal eyebrow lamination": "Facial (Blackhead Removal) + Eyebrow Lamination",
        "pmu lips": "PMU – Lips",
        "pmu eyebrows": "PMU – Eyebrows",
        "pmu eyeliner": "PMU – Eyeliner",
        "lip pmu touchup": "Lip PMU Touch-up",
        "deposit hold": "Deposit Hold",
    }

    service_facts: dict[str, dict[str, str]] = {
        "full body diode laser": {
            "en": "Most clients need about 6 sessions for best results.",
            "es": "La mayoría de los clientes necesitan aproximadamente 6 sesiones para mejores resultados.",
        },
        "full legs": {
            "en": "Most clients need about 6 sessions for best results.",
            "es": "La mayoría de los clientes necesitan aproximadamente 6 sesiones para mejores resultados.",
        },
        "lower legs": {
            "en": "Most clients need about 6 sessions for best results.",
            "es": "La mayoría de los clientes necesitan aproximadamente 6 sesiones para mejores resultados.",
        },
        "full arms": {
            "en": "Most clients need about 6 sessions for best results.",
            "es": "La mayoría de los clientes necesitan aproximadamente 6 sesiones para mejores resultados.",
        },
        "lower arms": {
            "en": "Most clients need about 6 sessions for best results.",
            "es": "La mayoría de los clientes necesitan aproximadamente 6 sesiones para mejores resultados.",
        },
        "brazilian bikini": {
            "en": "Most clients need about 6 sessions for best results.",
            "es": "La mayoría de los clientes necesitan aproximadamente 6 sesiones para mejores resultados.",
        },
        "full upper body diode laser men": {
            "en": "Most clients need about 6 sessions for best results.",
            "es": "La mayoría de los clientes necesitan aproximadamente 6 sesiones para mejores resultados.",
        },
    }

    return StructuredKnowledgeBase(
        data=data,
        aliases=aliases,
        display_names=display_names,
        service_facts=service_facts,
        service_registry=SERVICE_REGISTRY,
    )
