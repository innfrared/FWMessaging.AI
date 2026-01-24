from __future__ import annotations

from app.application.ports.service_catalog import ServiceCatalogPort


def build_duration_response(
    service_key: str,
    catalog: ServiceCatalogPort,
    language: str,
    include_price: bool = False,
) -> str:
    """Build duration response using service catalog."""
    entry = catalog.get_service(service_key)
    if not entry:
        if language == "es":
            return "No tengo información sobre la duración de este servicio."
        return "I don't have information about the duration of this service."

    duration_text = ""
    if entry.duration_minutes_max and entry.duration_minutes_max != entry.duration_minutes_min:
        duration_text = f"{entry.duration_minutes_min}–{entry.duration_minutes_max} minutes"
    else:
        duration_text = f"{entry.duration_minutes_min} minutes"

    service_name = entry.display_name

    if include_price:
        price_text = ""
        if entry.price_max and entry.price_max != entry.price_min:
            price_text = f"${entry.price_min}–${entry.price_max}"
        else:
            price_text = f"${entry.price_min}"

        if language == "es":
            return f"{service_name} toma aproximadamente {duration_text}. El precio es {price_text}."
        return f"{service_name} takes about {duration_text}. The price is {price_text}."

    if language == "es":
        return f"{service_name} toma aproximadamente {duration_text}."
    return f"{service_name} takes about {duration_text}."

