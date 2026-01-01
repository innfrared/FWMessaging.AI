from typing import Any

from app.application.ports.llm import LLMPort
from app.domain.entities.profile import Profile
from app.domain.entities.qa import QAItem
from app.domain.entities.evaluation import QuestionEvaluation, OverallEvaluation


class MockLLM(LLMPort):
    def generate_questions(self, profile: Profile, count: int, existing_questions: list[str], session_id: str) -> list[str]:
        mode_prefix = {
            "conversation": "Discuss",
            "drilldown": "Deep dive into",
            "case": "Scenario:",
            "challenge": "Challenge:",
            "retrospective": "Reflect on",
        }.get(profile.mode, "Discuss")
        
        base = [
            f"{mode_prefix} a core concept in {skill} for {profile.role}."
            for skill in list(profile.stack)[:count]
        ]
        if len(base) < count:
            base += [f"{mode_prefix} system design question #{i+1} for {profile.role}." for i in range(count - len(base))]
        existing_set = set(q.strip().lower() for q in existing_questions if q and q.strip())
        out = [q for q in base if q.strip().lower() not in existing_set]
        return out[:count]

    def evaluate_interview(
        self,
        items: list[QAItem],
        context: dict[str, Any],
        include_summary: bool,
        session_id: str,
    ) -> tuple[dict[int, QuestionEvaluation], OverallEvaluation | None]:
        results: dict[int, QuestionEvaluation] = {}
        for it in items:
            score = 7 if len(it.answer) > 20 else 5
            results[it.order] = QuestionEvaluation(
                order=it.order,
                score=score,
                feedback=f"Mock feedback for Q{it.order}.",
                meta={"len": len(it.answer)},
            )

        overall = None
        if include_summary:
            avg = round(sum(r.score for r in results.values()) / max(1, len(results)))
            overall = OverallEvaluation(
                score=avg,
                feedback="Mock overall feedback.",
                meta={"strengths": ["Communication"], "gaps": ["Depth"]},
            )

        return results, overall

