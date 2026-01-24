from __future__ import annotations

from app.application.ports.service_catalog import ServiceCatalogPort
from app.domain.entities.service_catalog import ServiceCatalogEntry
from app.infrastructure.knowledge.service_catalog_data import SERVICE_CATALOG


class ServiceCatalogStore(ServiceCatalogPort):
    def __init__(self, catalog: dict[str, ServiceCatalogEntry] | None = None) -> None:
        self._catalog = catalog or SERVICE_CATALOG

    def get_service(self, service_key: str) -> ServiceCatalogEntry | None:
        normalized_key = service_key.lower().strip()
        return self._catalog.get(normalized_key)

    def get_duration_minutes(self, service_key: str) -> int:
        entry = self.get_service(service_key)
        if not entry:
            return 60
        if entry.duration_minutes_max:
            return entry.duration_minutes_max
        return entry.duration_minutes_min

    def get_price_range(self, service_key: str) -> tuple[int, int | None] | None:
        entry = self.get_service(service_key)
        if not entry:
            return None
        return (entry.price_min or 0, entry.price_max)

