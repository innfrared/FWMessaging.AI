from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.service_catalog import ServiceCatalogEntry


class ServiceCatalogPort(ABC):
    @abstractmethod
    def get_service(self, service_key: str) -> ServiceCatalogEntry | None:
        """Get service catalog entry by service key."""
        raise NotImplementedError

    @abstractmethod
    def get_duration_minutes(self, service_key: str) -> int:
        """Get service duration in minutes. Returns max if range."""
        raise NotImplementedError

    @abstractmethod
    def get_price_range(self, service_key: str) -> tuple[int, int | None] | None:
        """Get service price range. Returns (min, max) or None if not found."""
        raise NotImplementedError

