"""
Same pattern as app/schemas/user.py: request and response shapes are
separate, and a client can never set status, current_question_index,
turns, resolved, or feedback — those exist only in the DB document,
written exclusively by app/services/interview_service.py reacting to
either auth (user_id) or Gemini's output (everything else). There is no
route anywhere that accepts those fields from a request body.

QuestionType is shared with app/services/ai.py's AIQuestionOut so the
"kind of question" vocabulary can't drift between what we ask Gemini for
and what we store/return.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

QuestionType = Literal["intro", "technical", "follow_up", "closing"]


class InterviewCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(min_length=1, max_length=100)
    years_experience: float = Field(ge=0, le=50)
    skills: list[str] = Field(default_factory=list, max_length=20)
    difficulty: Literal["easy", "medium", "hard"]


class TurnOut(BaseModel):
    index: int
    question: str
    question_type: QuestionType
    answer: Optional[str] = None
    answered_at: Optional[datetime] = None
    resolved: bool


class AnswerSubmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_index: int = Field(ge=0)
    answer: str = Field(min_length=1, max_length=5000)


class FeedbackOut(BaseModel):
    rating: int = Field(ge=1, le=5)
    rating_explanation: str
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]


class InterviewDetailOut(BaseModel):
    id: str
    # Reusing InterviewCreateIn here (rather than a fourth schema) is a
    # deliberate exception to "request and response shapes are always
    # separate": config is genuinely the same data in both directions —
    # an echo of what was submitted, not auth- or AI-derived like
    # everything else on this model.
    config: InterviewCreateIn
    status: Literal["in_progress", "completed"]
    current_question_index: int
    turns: list[TurnOut]
    feedback: Optional[FeedbackOut] = None
    created_at: datetime


class InterviewSummaryOut(BaseModel):
    """The history list needs enough to render one row per interview, not
    the full transcript — turns is a count here, not the array itself."""

    id: str
    config: InterviewCreateIn
    status: Literal["in_progress", "completed"]
    question_count: int
    created_at: datetime
