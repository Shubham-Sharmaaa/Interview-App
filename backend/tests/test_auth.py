"""
Focused on what M1 actually needs to prove, not exhaustive coverage:
- signup creates an account and never leaks the password hash
- a client cannot smuggle in a protected field (point 3 of the brief)
- duplicate emails are rejected
- login works, and fails the same way for a wrong email or wrong password
- the get_current_user dependency actually gates a route (M2/M3's ownership
  checks all build on this working correctly)

Tests are async because the `client` fixture (see conftest.py) is an
async httpx client — see conftest.py's docstring for why.
"""


async def test_signup_creates_user_and_returns_token(client):
    res = await client.post("/auth/signup", json={"email": "alice@example.com", "password": "correcthorse123"})

    assert res.status_code == 201
    body = res.json()
    assert body["user"]["email"] == "alice@example.com"
    assert "token" in body and len(body["token"]) > 0
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


async def test_signup_rejects_unexpected_fields(client):
    # extra="forbid" on UserSignupIn should reject this outright, not
    # silently drop the extra field — this is what makes "a client can
    # never set a protected field" an enforced rule, not just an intention.
    res = await client.post(
        "/auth/signup",
        json={"email": "carol@example.com", "password": "correcthorse123", "isAdmin": True},
    )
    assert res.status_code == 422


async def test_signup_rejects_duplicate_email(client):
    await client.post("/auth/signup", json={"email": "bob@example.com", "password": "correcthorse123"})
    res = await client.post("/auth/signup", json={"email": "bob@example.com", "password": "adifferentpassword"})
    assert res.status_code == 409


async def test_login_succeeds_with_correct_credentials(client):
    await client.post("/auth/signup", json={"email": "dave@example.com", "password": "correcthorse123"})
    res = await client.post("/auth/login", json={"email": "dave@example.com", "password": "correcthorse123"})
    assert res.status_code == 200
    assert "token" in res.json()


async def test_login_fails_with_wrong_password(client):
    await client.post("/auth/signup", json={"email": "erin@example.com", "password": "correcthorse123"})
    res = await client.post("/auth/login", json={"email": "erin@example.com", "password": "wrongpassword"})
    assert res.status_code == 401


async def test_login_fails_with_unknown_email(client):
    res = await client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
    assert res.status_code == 401


async def test_protected_route_requires_a_token(client):
    res = await client.get("/auth/me")
    assert res.status_code == 401


async def test_protected_route_rejects_a_garbage_token(client):
    res = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


async def test_protected_route_works_with_a_valid_token(client):
    signup_res = await client.post("/auth/signup", json={"email": "frank@example.com", "password": "correcthorse123"})
    token = signup_res.json()["token"]

    res = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "frank@example.com"
