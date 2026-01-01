from abc import ABC, abstractmethod
from typing import Any

from app.domain.entities.profile import Profile
from app.domain.entities.qa import QAItem
from app.domain.entities.evaluation import QuestionEvaluation, OverallEvaluation


class LLMPort(ABC):
    @abstractmethod
    def generate_questions(
        self,
        profile: Profile,
        count: int,
        existing_questions: list[str],
        session_id: str,
    ) -> list[str]:
        """
        Generate interview questions based on profile.

        Requirements:
        - May return more questions than `count`; use case will cap to `count`
        - May include duplicates; use case will deduplicate against `existing_questions` and within output
        - Should avoid questions already in `existing_questions` when possible
        - Return empty list if unable to generate questions

        Args:
            profile: Candidate profile (role, level, stack, mode)
            count: Target number of questions (adapter may return more)
            existing_questions: Questions to avoid duplicating
            session_id: Session identifier for context

        Returns:
            List of question strings (may be longer than count, may contain duplicates)
        """
        raise NotImplementedError

    @abstractmethod
    def evaluate_interview(
        self,
        items: list[QAItem],
        context: dict[str, Any],
        include_summary: bool,
        session_id: str,
    ) -> tuple[list[QuestionEvaluation], OverallEvaluation | None]:
        """
        Evaluate interview answers.

        Requirements:
        - Must return exactly one QuestionEvaluation per QAItem in `items`
        - Each QuestionEvaluation.order must match the corresponding QAItem.order
        - Return list of QuestionEvaluation objects
        - If `include_summary` is True, `overall` must be provided (not None)
        - All orders from input items must be present in returned list

        Args:
            items: List of QA items to evaluate (each has order, question, answer)
            context: Additional context for evaluation
            include_summary: Whether to generate overall summary
            session_id: Session identifier for context

        Returns:
            Tuple of (list of QuestionEvaluation, OverallEvaluation or None)
            - List must contain one QuestionEvaluation per QAItem.order
            - If include_summary=True, overall must not be None
        """
        raise NotImplementedError

