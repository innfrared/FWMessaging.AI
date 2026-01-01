from dataclasses import dataclass
from enum import Enum
from typing import Tuple


@dataclass(frozen=True)
class Profile:
    role: str
    level: str
    stack: Tuple[str, ...] = ()
    mode: str = "conversation"

    @staticmethod
    def from_payload(role: str, level: str, stack: list[str] | None, mode: str | Enum | None) -> "Profile":
        if isinstance(mode, Enum):
            mode = mode.value
        mode_str = str(mode or "conversation").strip().lower()
        
        normalized_stack = tuple(s.strip() for s in (stack or []) if s and s.strip())
        return Profile(
            role=(role or "").strip(),
            level=(level or "").strip(),
            stack=normalized_stack,
            mode=mode_str,
        )

