from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.application.exceptions import LLMContractError, LLMUpstreamError
from app.application.ports.llm import LLMPort
from app.core.config import settings
from app.domain.entities.evaluation import OverallEvaluation, QuestionEvaluation
from app.domain.entities.profile import Profile
from app.domain.entities.qa import QAItem
from app.infrastructure.llm.prompts import build_evaluate_prompt, build_generate_prompt


class OpenAILLM(LLMPort):
    """
    OpenAI-backed adapter implementing LLMPort.

    Contract guarantees:
    - generate_questions returns list[str]
    - evaluate_interview returns (list[QuestionEvaluation], OverallEvaluation|None)
    - Raises:
        LLMUpstreamError: networking/provider failures
        LLMContractError: invalid JSON or wrong schema/shape
    """

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate_questions(
        self,
        profile: Profile,
        count: int,
        existing_questions: list[str],
        session_id: str,
    ) -> list[str]:
        if count <= 0:
            return []

        prompt = build_generate_prompt(
            profile={
                "role": profile.role,
                "level": profile.level,
                "stack": list(profile.stack or []),
                "mode": profile.mode,
            },
            count=count,
            existing=existing_questions or [],
        )

        text = self._call_text(
            model=settings.OPENAI_MODEL_GENERATE,
            prompt=prompt,
            temperature=settings.OPENAI_TEMPERATURE_GENERATE,
            use_json_mode=True,
            session_id=session_id,
        )

        data = _parse_json(text, what="generate")

        if not isinstance(data, dict):
            raise LLMContractError("Generate: expected a JSON object with 'questions' key.")

        questions_raw = data.get("questions")
        if not isinstance(questions_raw, list):
            raise LLMContractError("Generate: 'questions' must be a list of strings.")

        out: list[str] = []
        for item in questions_raw:
            if not isinstance(item, str):
                raise LLMContractError("Generate: all items in 'questions' must be strings.")
            s = item.strip()
            if s:
                out.append(s)

        return out

    def evaluate_interview(
        self,
        items: list[QAItem],
        context: dict[str, Any],
        include_summary: bool,
        session_id: str,
    ) -> tuple[list[QuestionEvaluation], OverallEvaluation | None]:
        prompt = build_evaluate_prompt(
            context=context or {},
            items=[
                {"order": it.order, "question": it.question, "answer": it.answer}
                for it in items
            ],
            include_summary=bool(include_summary),
        )

        text = self._call_text(
            model=settings.OPENAI_MODEL_EVALUATE,
            prompt=prompt,
            temperature=settings.OPENAI_TEMPERATURE_EVALUATE,
            use_json_mode=True,
            session_id=session_id,
        )

        data = _parse_json(text, what="evaluate")

        if not isinstance(data, dict):
            raise LLMContractError("Evaluate: expected a JSON object with keys: results, overall.")

        results_raw = data.get("results")
        if not isinstance(results_raw, list):
            raise LLMContractError("Evaluate: 'results' must be a list.")

        results: list[QuestionEvaluation] = []
        seen_orders: set[int] = set()
        for r in results_raw:
            if not isinstance(r, dict):
                raise LLMContractError("Evaluate: each result must be an object.")
            try:
                order = int(r["order"])
                score = int(r["score"])
                feedback = str(r.get("feedback", ""))
                meta = r.get("meta") or {}
                if not isinstance(meta, dict):
                    raise TypeError("meta must be object")
            except Exception as e:
                raise LLMContractError(f"Evaluate: invalid result item shape: {e}")

            if order <= 0:
                raise LLMContractError("Evaluate: order must be >= 1.")
            if score < 0 or score > 10:
                raise LLMContractError("Evaluate: score must be 0-10.")
            if order in seen_orders:
                raise LLMContractError("Evaluate: duplicate order in results.")
            seen_orders.add(order)

            results.append(
                QuestionEvaluation(
                    order=order,
                    score=score,
                    feedback=feedback,
                    meta=meta,
                )
            )

        overall: OverallEvaluation | None = None
        overall_raw = data.get("overall", None)

        if include_summary:
            if overall_raw is None or not isinstance(overall_raw, dict):
                raise LLMContractError("Evaluate: include_summary=true but 'overall' is missing or invalid.")
            try:
                overall_score = int(overall_raw["score"])
                if overall_score < 0 or overall_score > 10:
                    raise LLMContractError("Evaluate: overall score must be 0-10.")
                overall = OverallEvaluation(
                    score=overall_score,
                    feedback=str(overall_raw.get("feedback", "")),
                    meta=dict(overall_raw.get("meta") or {}),
                )
            except LLMContractError:
                raise
            except Exception as e:
                raise LLMContractError(f"Evaluate: invalid overall shape: {e}")
        else:
            overall = None

        return results, overall

    def _call_text(self, model: str, prompt: str, temperature: float, use_json_mode: bool = False, session_id: str | None = None) -> str:
        try:
            system_content = "Return only valid JSON. Do not include markdown or extra text."
            if session_id:
                system_content += f" Session ID: {session_id}"
            
            kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": 1400,
            }
            if use_json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            resp = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            raise LLMUpstreamError(f"OpenAI API error: {e}") from e

        content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
        if not content:
            raise LLMContractError("LLM returned empty response text.")

        return content


def _parse_json(text: str, what: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        snippet = text[:200].replace("\n", " ")
        raise LLMContractError(f"{what.capitalize()}: invalid JSON. Snippet: {snippet!r}")

