from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import close_client, get_db
from app.routers import auth, interviews
from app.services.ai import close_ai_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Look up get_db through app.dependency_overrides first, falling back to
    # the real one. This one line is what lets tests (see tests/conftest.py)
    # register an override BEFORE the TestClient triggers this lifespan, so
    # the index below gets created on the isolated test database instead of
    # the real one — dependency_overrides only affects FastAPI's own
    # dependency-injection system, not a plain function call, so calling
    # get_db() directly here would otherwise silently ignore the override.
    db_dependency = app.dependency_overrides.get(get_db, get_db)
    db = await db_dependency()
    await db["users"].create_index("email", unique=True)
    # Not unique — many interviews per user. Speeds up the ownership-scoped
    # queries interview_service.py does, and the list query M5 adds later.
    await db["interviews"].create_index("user_id")

    yield

    await close_client()
    await close_ai_client()


app = FastAPI(title="AI Mock Interview API", lifespan=lifespan)

# Only explicitly listed origins are allowed — never "*". We're not using
# cookies for auth (see the auth design in the README), so credentials
# don't need to be enabled here. FRONTEND_ORIGIN can be comma-separated
# (e.g. local dev + the deployed Vercel URL at once), so you're not
# editing .env every time you switch between them.
allowed_origins = [origin.strip() for origin in settings.frontend_origin.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
async def health() -> dict:
    """
    Plain liveness check — deliberately does NOT touch the database or
    Gemini, so it stays fast and answers even if either dependency is
    having a bad moment. Useful for confirming the deployed backend is
    reachable at all, and for "waking up" Render's free tier before a demo.
    """
    return {"status": "ok"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
