"""
Database access via pymongo.AsyncMongoClient directly.

No Motor, no Beanie. See the project README for why: Motor was deprecated
in May 2025 in favor of PyMongo's own native async client, and for a
two-collection app, an ODM's abstraction wasn't worth a third library to
learn under a weekend deadline. We define our own thin Pydantic <-> dict
conversions in the schemas/ and services/ modules instead.

get_db() is a FastAPI dependency — routes that need the database declare
it as a parameter (`db=Depends(get_db)`) rather than importing a global,
which is what makes it easy to swap in the test database during tests
(see tests/conftest.py).
"""

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.config import settings

# One client for the whole app's lifetime, created once at import time.
# AsyncMongoClient is safe to share across requests on a single event loop
# (that's the whole point of it) but must NOT be shared across threads/processes.
_client: AsyncMongoClient = AsyncMongoClient(settings.mongodb_uri)


def get_client() -> AsyncMongoClient:
    return _client


async def get_db() -> AsyncDatabase:
    """FastAPI dependency: yields the application's real database."""
    return _client[settings.mongodb_db_name]


async def close_client() -> None:
    """Call this from the app's shutdown lifespan handler."""
    await _client.close()
