from dataclasses import dataclass
from typing import Any

from app.application.ports.llm import LLMPort
from app.application.ports.session_store import SessionStorePort
from app.application.exceptions import LLMContractError, LLMUpstreamError
from app.domain.entities.qa import QAItem


@dataclass
class EvaluateInterviewUseCase:
    llm: LLMPort
    store: SessionStorePort

    def execute(
        self,
        fastapi_session_id: str,
        items_payload: list[dict[str, Any]],
        context: dict[str, Any],
        include_summary: bool,
    ):
        items: list[QAItem] = []
        seen_orders: set[int] = set()
        
        for raw in items_payload:
            try:
                order = int(raw.get("order"))
            except (TypeError, ValueError):
                raise ValueError("Each item must include a valid integer 'order'.")
            
            if order <= 0:
                raise ValueError(f"Order must be >= 1, got {order}.")
            
            if order in seen_orders:
                raise ValueError(f"Duplicate order: {order}")
            seen_orders.add(order)
            
            items.append(
                QAItem.normalize(
                    order=order,
                    question=raw.get("question", ""),
                    answer=raw.get("answer", ""),
                )
            )

        missing = [it.order for it in items if not it.answer]
        if missing:
            raise ValueError(f"Missing answers for orders: {missing}")

        results, overall = self.llm.evaluate_interview(
            items=items,
            context=context or {},
            include_summary=bool(include_summary),
            session_id=fastapi_session_id,
        )

        results = results or []
        if not results:
            raise LLMContractError("LLM returned no evaluation results.")

        result_orders = [r.order for r in results]
        if len(set(result_orders)) != len(result_orders):
            raise LLMContractError("LLM returned duplicate orders in results.")

        requested_orders = {it.order for it in items}
        returned_orders = {r.order for r in results}

        if requested_orders != returned_orders:
            raise LLMContractError(
                f"LLM returned mismatched orders. Requested: {sorted(requested_orders)}, "
                f"Returned: {sorted(returned_orders)}"
            )

        if include_summary and overall is None:
            raise LLMContractError("LLM did not return overall summary when include_summary=true.")

        results_sorted = sorted(results, key=lambda r: r.order)

        self.store.put_evaluations(
            fastapi_session_id,
            evaluations=[
                {"order": r.order, "score": r.score, "feedback": r.feedback, "meta": r.meta}
                for r in results_sorted
            ],
        )

        return results_sorted, overall

