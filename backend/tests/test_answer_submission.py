"""
The core things §5/§6 of the implementation brief asked to be proven:
- ownership (a different user can't answer someone else's interview)
- duplicate/stale submissions are rejected cleanly, not silently duplicated
- an AI failure preserves the saved answer and a retry recovers cleanly,
  producing exactly one new turn, not zero and not two
- a full interview reaches completion with feedback after MAX_TURNS
"""

from app.services.interview_service import MAX_TURNS


async def _signup_and_get_token(client, email="riley@example.com"):
    res = await client.post("/auth/signup", json={"email": email, "password": "correcthorse123"})
    return res.json()["token"]


async def _create_interview(client, token):
    res = await client.post(
        "/interviews",
        json={"role": "Backend Engineer", "years_experience": 2, "skills": ["Python"], "difficulty": "medium"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return res.json()["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_submit_answer_advances_to_next_question(client):
    token = await _signup_and_get_token(client)
    interview_id = await _create_interview(client, token)

    res = await client.post(
        f"/interviews/{interview_id}/answer",
        json={"question_index": 0, "answer": "I recently built a small side project using FastAPI."},
        headers=_auth(token),
    )

    assert res.status_code == 200
    body = res.json()
    assert body["current_question_index"] == 1
    assert len(body["turns"]) == 2
    assert body["turns"][0]["resolved"] is True
    assert body["turns"][0]["answer"] == "I recently built a small side project using FastAPI."
    assert body["turns"][1]["resolved"] is False
    assert body["status"] == "in_progress"


async def test_submit_answer_rejects_unexpected_fields(client):
    token = await _signup_and_get_token(client)
    interview_id = await _create_interview(client, token)

    res = await client.post(
        f"/interviews/{interview_id}/answer",
        json={"question_index": 0, "answer": "hi", "resolved": True},
        headers=_auth(token),
    )
    assert res.status_code == 422


async def test_submit_answer_requires_auth(client):
    token = await _signup_and_get_token(client)
    interview_id = await _create_interview(client, token)

    res = await client.post(f"/interviews/{interview_id}/answer", json={"question_index": 0, "answer": "hi"})
    assert res.status_code == 401


async def test_submit_answer_404s_for_a_different_user(client):
    owner_token = await _signup_and_get_token(client, email="owner2@example.com")
    interview_id = await _create_interview(client, owner_token)

    other_token = await _signup_and_get_token(client, email="intruder@example.com")
    res = await client.post(
        f"/interviews/{interview_id}/answer",
        json={"question_index": 0, "answer": "not my interview"},
        headers=_auth(other_token),
    )
    assert res.status_code == 404


async def test_submit_answer_rejects_wrong_index(client):
    token = await _signup_and_get_token(client)
    interview_id = await _create_interview(client, token)

    res = await client.post(
        f"/interviews/{interview_id}/answer",
        json={"question_index": 3, "answer": "answering the wrong question"},
        headers=_auth(token),
    )
    assert res.status_code == 409
    assert res.json()["detail"]["reason"] == "stale_index"


async def test_resubmitting_an_already_resolved_answer_is_rejected_cleanly(client):
    token = await _signup_and_get_token(client)
    interview_id = await _create_interview(client, token)

    first = await client.post(
        f"/interviews/{interview_id}/answer",
        json={"question_index": 0, "answer": "first answer"},
        headers=_auth(token),
    )
    assert first.status_code == 200

    # A late/duplicate retry for the now-stale index 0 — the interview has
    # already moved on to index 1. Must not create a second turn.
    retry = await client.post(
        f"/interviews/{interview_id}/answer",
        json={"question_index": 0, "answer": "duplicate answer"},
        headers=_auth(token),
    )
    assert retry.status_code == 409

    check = await client.get(f"/interviews/{interview_id}", headers=_auth(token))
    assert len(check.json()["turns"]) == 2  # not 3


async def test_ai_failure_preserves_answer_and_retry_recovers(client, fake_ai):
    token = await _signup_and_get_token(client)
    interview_id = await _create_interview(client, token)

    fake_ai.should_fail = True
    failed = await client.post(
        f"/interviews/{interview_id}/answer",
        json={"question_index": 0, "answer": "an answer submitted during an outage"},
        headers=_auth(token),
    )
    assert failed.status_code == 502

    # The answer must have survived the failed AI call.
    mid_state = await client.get(f"/interviews/{interview_id}", headers=_auth(token))
    mid_body = mid_state.json()
    assert mid_body["turns"][0]["answer"] == "an answer submitted during an outage"
    assert mid_body["turns"][0]["resolved"] is False
    assert mid_body["current_question_index"] == 0  # never advanced
    assert len(mid_body["turns"]) == 1  # no second turn was created

    # Recovery: the exact same request, now that the AI is back.
    fake_ai.should_fail = False
    retry = await client.post(
        f"/interviews/{interview_id}/answer",
        json={"question_index": 0, "answer": "an answer submitted during an outage"},
        headers=_auth(token),
    )
    assert retry.status_code == 200
    retry_body = retry.json()
    assert retry_body["current_question_index"] == 1
    assert len(retry_body["turns"]) == 2  # exactly one new turn, not two
    assert retry_body["turns"][0]["resolved"] is True


async def test_full_interview_reaches_completion_with_feedback(client):
    token = await _signup_and_get_token(client)
    interview_id = await _create_interview(client, token)

    body = None
    for index in range(MAX_TURNS):
        res = await client.post(
            f"/interviews/{interview_id}/answer",
            json={"question_index": index, "answer": f"answer number {index}"},
            headers=_auth(token),
        )
        assert res.status_code == 200
        body = res.json()

    assert body["status"] == "completed"
    assert len(body["turns"]) == MAX_TURNS  # no extra turn appended after the last one
    assert body["feedback"] is not None
    assert 1 <= body["feedback"]["rating"] <= 5
    assert len(body["feedback"]["strengths"]) > 0

    # Completed interviews reject further answers outright.
    after_completion = await client.post(
        f"/interviews/{interview_id}/answer",
        json={"question_index": MAX_TURNS - 1, "answer": "too late"},
        headers=_auth(token),
    )
    assert after_completion.status_code == 409
