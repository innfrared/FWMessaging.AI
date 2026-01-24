from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceCatalogEntry:
    service_key: str
    display_name: str
    category: str
    price_min: int | None
    price_max: int | None
    duration_minutes_min: int
    duration_minutes_max: int | None
    notes: str | None = None

