"""
M2 scope: creating an interview and fetching it back, both authenticated
and ownership-scoped. The AI is always the fake from tests/fakes.py here
— never a real call.
"""


async def _signup_and_get_token(client, email="quinn@example.com"):
    res = await client.post("/auth/signup", json={"email": email, "password": "correcthorse123"})
    return res.json()["token"]


async def test_create_interview_returns_opening_question(client):
    token = await _signup_and_get_token(client)

    res = await client.post(
        "/interviews",
        json={"role": "Backend Engineer", "years_experience": 1, "skills": ["Python", "SQL"], "difficulty": "medium"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "in_progress"
    assert body["current_question_index"] == 0
    assert len(body["turns"]) == 1
    assert body["turns"][0]["question_type"] == "intro"
    assert body["turns"][0]["answer"] is None
    assert body["turns"][0]["resolved"] is False
    assert body["feedback"] is None


async def test_create_interview_rejects_unexpected_fields(client):
    token = await _signup_and_get_token(client)

    # A client trying to set status/turns/userId directly should be
    # rejected outright — same extra="forbid" enforcement as signup.
    res = await client.post(
        "/interviews",
        json={
            "role": "Backend Engineer",
            "years_experience": 1,
            "skills": [],
            "difficulty": "medium",
            "status": "completed",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


async def test_create_interview_requires_auth(client):
    res = await client.post(
        "/interviews",
        json={"role": "Backend Engineer", "years_experience": 1, "skills": [], "difficulty": "medium"},
    )
    assert res.status_code == 401


async def test_get_interview_returns_what_was_created(client):
    token = await _signup_and_get_token(client)
    create_res = await client.post(
        "/interviews",
        json={"role": "Backend Engineer", "years_experience": 1, "skills": [], "difficulty": "easy"},
        headers={"Authorization": f"Bearer {token}"},
    )
    interview_id = create_res.json()["id"]

    res = await client.get(f"/interviews/{interview_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["id"] == interview_id


async def test_get_interview_404s_for_a_different_user(client):
    owner_token = await _signup_and_get_token(client, email="owner@example.com")
    create_res = await client.post(
        "/interviews",
        json={"role": "Backend Engineer", "years_experience": 1, "skills": [], "difficulty": "easy"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    interview_id = create_res.json()["id"]

    other_token = await _signup_and_get_token(client, email="someone-else@example.com")
    res = await client.get(f"/interviews/{interview_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert res.status_code == 404


async def test_get_interview_404s_for_a_nonexistent_id(client):
    token = await _signup_and_get_token(client)
    res = await client.get("/interviews/000000000000000000000000", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


async def test_get_interview_404s_for_a_malformed_id(client):
    # Not a valid ObjectId at all — should 404, not 500.
    token = await _signup_and_get_token(client)
    res = await client.get("/interviews/not-an-id", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404
