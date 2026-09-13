"""
Why a real (isolated) database instead of mocking pymongo: the atomic
conditional updates we'll write in M3 (the answer/retry state machine)
depend on exact MongoDB query-matching semantics — the $elemMatch trap
described in the project README is a good example of behavior a mock
would have to reimplement perfectly to be trustworthy. Given
AsyncMongoClient is new enough (GA since 2025) that no mocking library
for it is battle-tested yet, testing against real MongoDB is both safer
and less work than trusting a mock to be right.

So: every test runs against a second database on the same free Atlas
cluster (MONGODB_TEST_DB_NAME in .env), wiped clean before and after.
"""

import httpx
import pytest
from asgi_lifespan import LifespanManager
from pymongo import AsyncMongoClient

from app.config import settings
from app.db import get_db
from app.main import app
from app.services.ai import get_ai_service
from tests.fakes import FakeAIService


@pytest.fixture
async def clean_test_db():
    test_client = AsyncMongoClient(settings.mongodb_uri)
    db = test_client[settings.mongodb_test_db_name]

    async def wipe():
        for name in await db.list_collection_names():
            await db.drop_collection(name)

    await wipe()
    yield db
    await wipe()
    await test_client.close()


@pytest.fixture
def fake_ai():
    """A single FakeAIService instance for the test, exposed as its own
    fixture so a test can request it alongside `client` and flip
    `fake_ai.should_fail` between requests — e.g. to simulate an AI outage
    on one submission and a recovery on the retry. `client` wires this
    exact instance into the app; requesting `fake_ai` in a test gets the
    same one, since pytest caches fixtures per test."""
    return FakeAIService()


@pytest.fixture
async def client(clean_test_db, fake_ai):
    """
    An async httpx client talking to the app in-process, instead of
    fastapi.testclient.TestClient. This matters specifically because our
    DB client is async-native: TestClient runs the ASGI app (including our
    lifespan) in its own background thread with its own event loop, so an
    AsyncMongoClient created in *this* fixture (bound to pytest-asyncio's
    event loop for this test, via the wipe() calls above) would be used
    from a *different* loop the moment the app's lifespan or a route
    handler touched it — exactly the "Cannot use AsyncMongoClient in
    different event loop" error. httpx.AsyncClient + ASGITransport runs
    the app in-process in the caller's own event loop instead, so the
    fixture, the lifespan, and every request all share one loop.

    ASGITransport alone doesn't trigger FastAPI's startup/shutdown
    lifespan the way `with TestClient(app)` used to — LifespanManager is
    the standard small library for driving that explicitly.

    Overrides get_ai_service with the fake_ai fixture's instance — always
    the SAME instance across every request in the test (not a fresh one
    per call), which is what lets a test flip should_fail mid-test and
    have it actually take effect on the next request.

    The overrides are registered before LifespanManager starts the app,
    so main.py's index creation also lands on the test database — see
    the comment in app/main.py's lifespan.
    """

    async def get_test_db():
        return clean_test_db

    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_ai_service] = lambda: fake_ai

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac

    app.dependency_overrides.clear()
