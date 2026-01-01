from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QuestionEvaluation:
    order: int
    score: int
    feedback: str
    meta: dict[str, Any]


@dataclass(frozen=True)
class OverallEvaluation:
    score: int
    feedback: str
    meta: dict[str, Any]

