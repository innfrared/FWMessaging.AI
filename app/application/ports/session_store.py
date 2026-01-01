from abc import ABC, abstractmethod
from typing import Any


class SessionStorePort(ABC):
    @abstractmethod
    def get_or_create(self, session_id: str | None) -> str:
        raise NotImplementedError

    @abstractmethod
    def put_questions(self, session_id: str, questions: list[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_questions(self, session_id: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def put_evaluations(self, session_id: str, evaluations: list[dict[str, Any]]) -> None:
        raise NotImplementedError

