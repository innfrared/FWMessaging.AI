from fastapi import APIRouter, Depends, HTTPException
from app.api.v1.schemas import (
    GenerateRequestSchema, GenerateResponseSchema,
    EvaluateRequestSchema, EvaluateResponseSchema,
    QuestionEvaluationSchema, OverallEvaluationSchema,
)
from app.wiring.dependencies import get_generate_use_case, get_evaluate_use_case
from app.application.use_cases.generate_questions import GenerateQuestionsUseCase
from app.application.use_cases.evaluate_interview import EvaluateInterviewUseCase
from app.application.exceptions import LLMUpstreamError, LLMContractError

router = APIRouter()


@router.post("/generate", response_model=GenerateResponseSchema)
def generate(
    req: GenerateRequestSchema,
    uc: GenerateQuestionsUseCase = Depends(get_generate_use_case),
):
    try:
        session_id, questions = uc.execute(
            fastapi_session_id=req.fastapi_session_id,
            profile_payload=req.profile.model_dump(mode="json"),
            count=req.count,
            existing_questions=req.existing_questions,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (LLMUpstreamError, LLMContractError) as e:
        raise HTTPException(status_code=502, detail=str(e))
    
    return GenerateResponseSchema(fastapi_session_id=session_id, questions=questions)


@router.post("/evaluate", response_model=EvaluateResponseSchema)
def evaluate(
    req: EvaluateRequestSchema,
    uc: EvaluateInterviewUseCase = Depends(get_evaluate_use_case),
):
    try:
        ctx = dict(req.context or {})
        ctx.pop("mode", None)
        ctx["mode"] = req.mode.value
        results, overall = uc.execute(
            fastapi_session_id=req.fastapi_session_id,
            items_payload=[i.model_dump(mode="json") for i in req.items],
            context=ctx,
            include_summary=req.include_summary,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (LLMUpstreamError, LLMContractError) as e:
        raise HTTPException(status_code=502, detail=str(e))

    return EvaluateResponseSchema(
        results=[
            QuestionEvaluationSchema(order=r.order, score=r.score, feedback=r.feedback, meta=r.meta)
            for r in results
        ],
        overall=(
            OverallEvaluationSchema(score=overall.score, feedback=overall.feedback, meta=overall.meta)
            if overall else None
        ),
    )

