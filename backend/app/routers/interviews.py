from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from app.db import get_db
from app.deps import get_current_user
from app.rate_limit import check_rate_limit
from app.schemas.interview import AnswerSubmitIn, InterviewCreateIn, InterviewDetailOut, InterviewSummaryOut
from app.schemas.user import UserOut
from app.services import interview_service
from app.services.ai import AIService, AIServiceError, get_ai_service

router = APIRouter()


@router.post("", response_model=InterviewDetailOut, status_code=201)
async def create_interview(
    body: InterviewCreateIn,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> InterviewDetailOut:
    # Shared key with submit_answer below: both consume the same Gemini
    # quota, so they share one budget rather than each getting their own.
    check_rate_limit(f"ai:{current_user.id}")
    try:
        return await interview_service.create_interview(db, ai, current_user.id, body)
    except AIServiceError:
        raise HTTPException(status_code=502, detail="The interviewer hit a snag generating your first question. Please retry.")


@router.get("", response_model=list[InterviewSummaryOut])
async def list_interviews(
    current_user: UserOut = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> list[InterviewSummaryOut]:
    return await interview_service.list_interviews(db, current_user.id)


@router.get("/{interview_id}", response_model=InterviewDetailOut)
async def get_interview(
    interview_id: str,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> InterviewDetailOut:
    result = await interview_service.get_interview(db, current_user.id, interview_id)
    if result is None:
        # Same 404 whether the interview doesn't exist or belongs to
        # someone else — see the docstring on interview_service.get_interview.
        raise HTTPException(status_code=404, detail="Interview not found")
    return result


@router.post("/{interview_id}/answer", response_model=InterviewDetailOut)
async def submit_answer(
    interview_id: str,
    body: AnswerSubmitIn,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> InterviewDetailOut:
    check_rate_limit(f"ai:{current_user.id}")
    try:
        return await interview_service.submit_answer(
            db, ai, current_user.id, interview_id, body.question_index, body.answer
        )
    except interview_service.InterviewNotFoundError:
        raise HTTPException(status_code=404, detail="Interview not found")
    except interview_service.StaleSubmissionError as e:
        # The client's correct response to this is to reconcile its UI to
        # currentState, not treat it as a hard error — see the docstring
        # on StaleSubmissionError.
        raise HTTPException(
            status_code=409,
            detail={"reason": "stale_index", "currentState": e.current_state.model_dump(mode="json")},
        )
    except AIServiceError:
        # The answer is already saved (see submit_answer's docstring) —
        # this exact same request is safe for the client to resend.
        raise HTTPException(
            status_code=502,
            detail="The interviewer hit a snag. Your answer was saved — please retry.",
        )
