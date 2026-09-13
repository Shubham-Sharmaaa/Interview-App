from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.db import get_db
from app.deps import get_current_user
from app.schemas.user import TokenOut, UserLoginIn, UserOut, UserSignupIn
from app.security import create_access_token, hash_password, verify_password

router = APIRouter()


@router.post("/signup", response_model=TokenOut, status_code=201)
async def signup(body: UserSignupIn, db: AsyncDatabase = Depends(get_db)) -> TokenOut:
    # Cheap check first, for the common case and a clear error message.
    existing = await db["users"].find_one({"email": body.email})
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    doc = {
        "email": body.email,
        "password_hash": hash_password(body.password),
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = await db["users"].insert_one(doc)
    except DuplicateKeyError:
        # The check above isn't atomic with the insert — two signups for the same
        # email could race between them. The unique index created at startup
        # (see app/main.py) is what actually prevents a duplicate account; this
        # catch just turns that into the same clean 409 instead of a 500.
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user_out = UserOut(id=str(result.inserted_id), email=body.email, created_at=doc["created_at"])
    token, expires_at = create_access_token(str(result.inserted_id))
    return TokenOut(user=user_out, token=token, expires_at=expires_at)


@router.post("/login", response_model=TokenOut)
async def login(body: UserLoginIn, db: AsyncDatabase = Depends(get_db)) -> TokenOut:
    doc = await db["users"].find_one({"email": body.email})

    # Same error for "no such email" and "wrong password" — don't give an
    # attacker a way to enumerate which emails have accounts.
    if doc is None or not verify_password(body.password, doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    user_out = UserOut(id=str(doc["_id"]), email=doc["email"], created_at=doc["created_at"])
    token, expires_at = create_access_token(str(doc["_id"]))
    return TokenOut(user=user_out, token=token, expires_at=expires_at)


@router.get("/me", response_model=UserOut)
async def me(current_user: UserOut = Depends(get_current_user)) -> UserOut:
    """Lets the frontend check 'am I still logged in' on app load, and doubles
    as the simplest possible proof that the auth dependency works end to end."""
    return current_user
