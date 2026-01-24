from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SelectionState:
    status: str = "none"  # "none", "awaiting_service_choice", "service_selected"
    pending_category: str | None = None  # e.g., "laser", "brows", "facial", "lashes", "pmu"
    selected_service_key: str | None = None  # canonical service registry key
    last_service_mention: str | None = None  # raw user text
    updated_at: float | None = None

