from enum import Enum
from pydantic import BaseModel, Field
from typing import Any


class Mode(str, Enum):
    conversation = "conversation"
    drilldown = "drilldown"
    case = "case"
    challenge = "challenge"
    retrospective = "retrospective"


class ProfileSchema(BaseModel):
    role: str
    level: str
    stack: list[str] = Field(default_factory=list)
    mode: Mode = Mode.conversation


class GenerateRequestSchema(BaseModel):
    fastapi_session_id: str | None = None
    profile: ProfileSchema
    count: int = 5
    existing_questions: list[str] = Field(default_factory=list)


class GenerateResponseSchema(BaseModel):
    fastapi_session_id: str
    questions: list[str]


class QAItemSchema(BaseModel):
    order: int
    question: str
    answer: str


class EvaluateRequestSchema(BaseModel):
    fastapi_session_id: str
    items: list[QAItemSchema] = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    mode: Mode = Mode.conversation
    include_summary: bool = True


class QuestionEvaluationSchema(BaseModel):
    order: int
    score: int
    feedback: str
    meta: dict[str, Any] = Field(default_factory=dict)


class OverallEvaluationSchema(BaseModel):
    score: int
    feedback: str
    meta: dict[str, Any] = Field(default_factory=dict)


class EvaluateResponseSchema(BaseModel):
    results: list[QuestionEvaluationSchema]
    overall: OverallEvaluationSchema | None = None

