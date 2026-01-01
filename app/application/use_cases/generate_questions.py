from dataclasses import dataclass

from app.application.ports.llm import LLMPort
from app.application.ports.session_store import SessionStorePort
from app.domain.entities.profile import Profile

MAX_GENERATE_COUNT = 50


@dataclass
class GenerateQuestionsUseCase:
    llm: LLMPort
    store: SessionStorePort

    def execute(
        self,
        fastapi_session_id: str | None,
        profile_payload: dict,
        count: int,
        existing_questions: list[str],
    ) -> tuple[str, list[str]]:
        session_id = self.store.get_or_create(fastapi_session_id)

        count_value = max(0, int(count))
        count_value = min(count_value, MAX_GENERATE_COUNT)

        if count_value <= 0:
            self.store.put_questions(session_id, [])
            return session_id, []

        profile = Profile.from_payload(
            role=profile_payload.get("role"),
            level=profile_payload.get("level"),
            stack=profile_payload.get("stack"),
            mode=profile_payload.get("mode"),
        )

        existing = [q.strip() for q in (existing_questions or []) if q and q.strip()]
        seen = set(q.lower() for q in existing)

        questions = self.llm.generate_questions(
            profile=profile,
            count=count_value,
            existing_questions=existing,
            session_id=session_id,
        ) or []

        cleaned: list[str] = []
        for q in questions:
            q_clean = q.strip()
            if q_clean and q_clean.lower() not in seen:
                cleaned.append(q_clean)
                seen.add(q_clean.lower())
            if len(cleaned) >= count_value:
                break

        self.store.put_questions(session_id, cleaned)

        return session_id, cleaned

