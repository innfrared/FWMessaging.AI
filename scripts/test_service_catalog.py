from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.application.utils.duration_answer import build_duration_response
from app.infrastructure.knowledge.service_catalog_store import ServiceCatalogStore


def test_catalog_lookup():
    catalog = ServiceCatalogStore()

    entry = catalog.get_service("full body diode laser")
    assert entry is not None
    assert entry.display_name == "Full Body Diode Laser"
    assert entry.price_min == 150
    assert entry.duration_minutes_min == 60
    print("✅ Catalog lookup test passed")


def test_duration_retrieval():
    catalog = ServiceCatalogStore()

    duration = catalog.get_duration_minutes("full body diode laser")
    assert duration == 60

    duration_range = catalog.get_duration_minutes("facial deep blackhead removal")
    assert duration_range == 90
    print("✅ Duration retrieval test passed")


def test_price_retrieval():
    catalog = ServiceCatalogStore()

    price_range = catalog.get_price_range("full body diode laser")
    assert price_range == (150, 150)

    price_range = catalog.get_price_range("facial deep blackhead removal")
    assert price_range == (120, 150)
    print("✅ Price retrieval test passed")


def test_duration_response():
    catalog = ServiceCatalogStore()

    response = build_duration_response("full body diode laser", catalog, "en", include_price=False)
    assert "60 minutes" in response
    assert "Full Body Diode Laser" in response

    response = build_duration_response("full body diode laser", catalog, "en", include_price=True)
    assert "60 minutes" in response
    assert "$150" in response

    response = build_duration_response("facial deep blackhead removal", catalog, "en", include_price=False)
    assert "60–90 minutes" in response or "60-90 minutes" in response
    print("✅ Duration response test passed")


if __name__ == "__main__":
    test_catalog_lookup()
    test_duration_retrieval()
    test_price_retrieval()
    test_duration_response()
    print("\n✅ All service catalog tests passed!")

