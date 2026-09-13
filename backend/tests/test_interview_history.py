"""
M5 scope: GET /interviews. Ownership is the one that matters most here —
the same principle as everywhere else, applied to a list this time
instead of a single document.
"""


async def _signup_and_get_token(client, email="hist@example.com"):
    res = await client.post("/auth/signup", json={"email": email, "password": "correcthorse123"})
    return res.json()["token"]


async def _create_interview(client, token, role="Backend Engineer", difficulty="easy"):
    res = await client.post(
        "/interviews",
        json={"role": role, "years_experience": 1, "skills": [], "difficulty": difficulty},
        headers={"Authorization": f"Bearer {token}"},
    )
    return res.json()


async def test_list_interviews_starts_empty(client):
    token = await _signup_and_get_token(client)
    res = await client.get("/interviews", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == []


async def test_list_interviews_returns_created_ones_most_recent_first(client):
    token = await _signup_and_get_token(client)
    await _create_interview(client, token, role="Backend Engineer")
    await _create_interview(client, token, role="Frontend Engineer")

    res = await client.get("/interviews", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert body[0]["config"]["role"] == "Frontend Engineer"  # created second, listed first
    assert body[1]["config"]["role"] == "Backend Engineer"
    assert body[0]["question_count"] == 1  # just the opening question so far


async def test_list_interviews_only_shows_own(client):
    token_a = await _signup_and_get_token(client, email="owner-a@example.com")
    await _create_interview(client, token_a)

    token_b = await _signup_and_get_token(client, email="owner-b@example.com")
    res = await client.get("/interviews", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 200
    assert res.json() == []


async def test_list_interviews_requires_auth(client):
    res = await client.get("/interviews")
    assert res.status_code == 401
