"""
Interview creation, retrieval, and the answer/retry state machine all live
here, not in the router, so app/routers/interviews.py stays focused on
HTTP concerns (status codes, response models) while this module owns what
an interview document actually looks like and how it changes.

The state machine (submit_answer) implements the design from the
implementation brief:

  current_question_index always points at the ONE turn that's either
  awaiting an answer or awaiting AI resolution. That turn is in exactly
  one of two states while it holds that position:
    - answer is None            -> fresh, awaiting the candidate's answer
    - answer is set, resolved is False -> answer saved, awaiting (or
      retrying, after a prior failure) the AI call that turns it into the
      next question or the final feedback

  It is never resolved=True while still current -- resolving is exactly
  the action that advances current_question_index away from it. That
  invariant is what makes retries safe: a retried request for the same
  index either finds the answer already saved (no-op, proceed straight to
  the AI call) or finds the turn already resolved and the index moved on
  (which can't happen while still "current" -- see StaleSubmissionError).
"""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.database import AsyncDatabase

from app.schemas.interview import InterviewCreateIn, InterviewDetailOut, InterviewSummaryOut, TurnOut
from app.services.ai import AIService, AIServiceError

# 1 intro + 4 technical/follow-up + 1 explicitly-flagged closing question,
# then feedback. Small enough to be a "sensible, bounded" interview, large
# enough to feel like real practice.
MAX_TURNS = 6


class InterviewNotFoundError(Exception):
    """No such interview, a malformed id, or it belongs to a different
    user -- the router turns all three into the same 404 so a user
    probing an id that isn't theirs can't tell which case it was."""


class StaleSubmissionError(Exception):
    """The submitted question_index doesn't match current_question_index,
    or the interview is already completed. Carries the interview's actual
    current state so the router can hand it back to the client -- the
    correct client response is to reconcile its UI to this state, not
    treat it as a hard failure (this is what makes a lost success
    response, followed by a client retry, safe: the retry gets a clean
    409 with the real state instead of a silent duplicate)."""

    def __init__(self, current_state: InterviewDetailOut):
        self.current_state = current_state


def _doc_to_out(doc: dict) -> InterviewDetailOut:
    return InterviewDetailOut(
        id=str(doc["_id"]),
        config=InterviewCreateIn(**doc["config"]),
        status=doc["status"],
        current_question_index=doc["current_question_index"],
        turns=[TurnOut(**t) for t in doc["turns"]],
        feedback=doc["feedback"],
        created_at=doc["created_at"],
    )


def _build_transcript(turns: list[dict]) -> str:
    lines = []
    for t in turns:
        lines.append(f"Q{t['index'] + 1} ({t['question_type']}): {t['question']}")
        if t["answer"] is not None:
            lines.append(f"A{t['index'] + 1}: {t['answer']}")
    return "\n".join(lines)


async def create_interview(
    db: AsyncDatabase, ai: AIService, user_id: str, body: InterviewCreateIn
) -> InterviewDetailOut:
    # AIServiceError propagates to the router uncaught -> 502. Nothing is
    # written to the database until after this succeeds, so a failure here
    # leaves nothing behind to clean up.
    opening = await ai.generate_opening_question(body.model_dump())

    doc = {
        "user_id": ObjectId(user_id),
        "config": body.model_dump(),
        "status": "in_progress",
        "current_question_index": 0,
        "turns": [
            {
                "index": 0,
                "question": opening.question,
                "question_type": opening.question_type,
                "answer": None,
                "answered_at": None,
                "resolved": False,
            }
        ],
        "feedback": None,
        "created_at": datetime.now(timezone.utc),
    }

    result = await db["interviews"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_out(doc)


async def get_interview(db: AsyncDatabase, user_id: str, interview_id: str) -> InterviewDetailOut | None:
    """Returns None for both 'no such interview' and 'not yours' — the
    router turns either case into the same 404, so a user probing an ID
    that isn't theirs can't even tell whether it exists."""
    try:
        object_id = ObjectId(interview_id)
    except InvalidId:
        return None

    doc = await db["interviews"].find_one({"_id": object_id})
    if doc is None or str(doc["user_id"]) != user_id:
        return None

    return _doc_to_out(doc)


async def list_interviews(db: AsyncDatabase, user_id: str) -> list[InterviewSummaryOut]:
    """Most recent first. Scoped to user_id in the query itself, not just
    filtered after the fact — same ownership principle as everywhere else."""
    docs = await db["interviews"].find({"user_id": ObjectId(user_id)}).sort("created_at", -1).to_list(None)
    return [
        InterviewSummaryOut(
            id=str(doc["_id"]),
            config=InterviewCreateIn(**doc["config"]),
            status=doc["status"],
            question_count=len(doc["turns"]),
            created_at=doc["created_at"],
        )
        for doc in docs
    ]


async def submit_answer(
    db: AsyncDatabase,
    ai: AIService,
    user_id: str,
    interview_id: str,
    question_index: int,
    answer_text: str,
) -> InterviewDetailOut:
    try:
        interview_oid = ObjectId(interview_id)
    except InvalidId:
        raise InterviewNotFoundError()

    doc = await db["interviews"].find_one({"_id": interview_oid})
    if doc is None or str(doc["user_id"]) != user_id:
        raise InterviewNotFoundError()
    if doc["status"] == "completed" or question_index != doc["current_question_index"]:
        raise StaleSubmissionError(_doc_to_out(doc))

    # Retry-safe save: $elemMatch (not plain dot-notation on two fields,
    # which can match across *different* array elements) requires the
    # SAME element to satisfy both conditions. If the answer's already
    # saved -- a retry after the AI call failed last time -- this matches
    # nothing and no-ops, which is exactly the behavior we want.
    await db["interviews"].update_one(
        {"_id": interview_oid, "turns": {"$elemMatch": {"index": question_index, "answer": None}}},
        {"$set": {"turns.$.answer": answer_text, "turns.$.answered_at": datetime.now(timezone.utc)}},
    )

    # Re-fetch: we want the answer regardless of whether *this* request's
    # write landed just now or an earlier attempt already saved it.
    doc = await db["interviews"].find_one({"_id": interview_oid})
    transcript = _build_transcript(doc["turns"])
    is_last = question_index == MAX_TURNS - 1

    try:
        if is_last:
            feedback = await ai.generate_feedback(transcript)
        else:
            next_index = question_index + 1
            next_question = await ai.generate_next_turn(transcript, is_last_question=next_index == MAX_TURNS - 1)
    except AIServiceError:
        # Nothing beyond the answer save above was touched. resolved is
        # still False, so the exact same request is safe to resend -- it
        # will find the answer already saved (no-op) and just retry the
        # AI call. The router turns this into a 502.
        raise

    # $elemMatch on resolved=False guards a race: if two requests both got
    # this far concurrently, only the first update matches (resolved is
    # still False); the second's matched_count is 0 and it just falls
    # through to re-fetch and return the winner's already-decided result,
    # instead of appending a second turn or overwriting the feedback.
    #
    # The two branches below are NOT symmetric in shape, and that's
    # deliberate: the "last question" branch only ever needs $set (mark
    # resolved, complete the interview, attach feedback) — all on fields
    # that don't overlap, so one update document is fine. The "more
    # questions to go" branch needs to both mark the current turn resolved
    # (a $set on turns.$.resolved) AND append the next turn (a $push on
    # turns) — and MongoDB refuses to combine those in a single update
    # document: "turns" is a literal prefix of "turns.$.resolved", and two
    # different operators are not allowed to touch overlapping paths in
    # one call, full stop. That's what produced the WriteError.
    #
    # The fix is two sequential update_one calls instead of one. This does
    # NOT weaken the concurrency guarantee: the $elemMatch(resolved=False)
    # filter is still what decides the race, on the FIRST call. MongoDB
    # serializes concurrent writes to the same document, so at most one
    # concurrent request can match that filter and flip resolved to True.
    # Only that winner ever reaches the second call, so the $push is
    # unconditional there *because* the first call already established
    # exclusivity — a second concurrent request simply gets matched_count
    # 0 on the first call and skips the push entirely, falling through to
    # re-fetch and return the winner's state, exactly as before.
    if is_last:
        await db["interviews"].update_one(
            {"_id": interview_oid, "turns": {"$elemMatch": {"index": question_index, "resolved": False}}},
            {
                "$set": {
                    "turns.$.resolved": True,
                    "status": "completed",
                    "feedback": feedback.model_dump(),
                }
            },
        )
    else:
        next_index = question_index + 1
        resolve_result = await db["interviews"].update_one(
            {"_id": interview_oid, "turns": {"$elemMatch": {"index": question_index, "resolved": False}}},
            {"$set": {"turns.$.resolved": True, "current_question_index": next_index}},
        )
        if resolve_result.matched_count == 1:
            await db["interviews"].update_one(
                {"_id": interview_oid},
                {
                    "$push": {
                        "turns": {
                            "index": next_index,
                            "question": next_question.question,
                            "question_type": next_question.question_type,
                            "answer": None,
                            "answered_at": None,
                            "resolved": False,
                        }
                    }
                },
            )
        # matched_count == 0 means a concurrent request already resolved
        # this turn and (by the same logic) already pushed the next one —
        # nothing to do here but fall through to re-fetch below.

    doc = await db["interviews"].find_one({"_id": interview_oid})
    return _doc_to_out(doc)
