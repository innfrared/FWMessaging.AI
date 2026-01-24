from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Reply:
    text: str
    should_handoff: bool
    handoff_reason: str
    meta: dict[str, Any]
