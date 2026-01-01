import uuid
from typing import Any

from app.application.ports.session_store import SessionStorePort


class MemorySessionStore(SessionStorePort):
    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def get_or_create(self, session_id: str | None) -> str:
        if session_id and session_id in self._sessions:
            return session_id
        new_id = f"fa_{uuid.uuid4().hex}"
        self._sessions[new_id] = {"questions": [], "evaluations": []}
        return new_id

    def put_questions(self, session_id: str, questions: list[str]) -> None:
        self._sessions.setdefault(session_id, {"questions": [], "evaluations": []})
        self._sessions[session_id]["questions"] = list(questions)

    def get_questions(self, session_id: str) -> list[str]:
        return list(self._sessions.get(session_id, {}).get("questions", []))

    def put_evaluations(self, session_id: str, evaluations: list[dict[str, Any]]) -> None:
        self._sessions.setdefault(session_id, {"questions": [], "evaluations": []})
        self._sessions[session_id]["evaluations"] = list(evaluations)

