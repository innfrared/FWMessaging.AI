from functools import lru_cache

from app.core.config import settings
from app.infrastructure.llm.mock_llm import MockLLM
from app.infrastructure.llm.openai_llm import OpenAILLM
from app.infrastructure.store.memory_store import MemorySessionStore
from app.application.use_cases.generate_questions import GenerateQuestionsUseCase
from app.application.use_cases.evaluate_interview import EvaluateInterviewUseCase


_store = MemorySessionStore()


@lru_cache
def get_llm():
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
        return OpenAILLM()
    return MockLLM()


def get_generate_use_case() -> GenerateQuestionsUseCase:
    return GenerateQuestionsUseCase(llm=get_llm(), store=_store)


def get_evaluate_use_case() -> EvaluateInterviewUseCase:
    return EvaluateInterviewUseCase(llm=get_llm(), store=_store)

