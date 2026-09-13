"""
get_current_user is a FastAPI dependency: any route that declares
`current_user: UserOut = Depends(get_current_user)` gets this run first.
It's the direct equivalent of an Express auth middleware that reads a
token and attaches req.user — except FastAPI wires it per-route via
dependency injection rather than a global middleware chain.

Notice this re-fetches the user from the database on every request rather
than trusting the token's contents beyond the user id. The token is a
*claim* ("I am user X"), not a guarantee that user X still exists or
still has the same data — re-checking against the database means a
deleted user's token stops working immediately, not just at expiry.
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from bson import ObjectId
from bson.errors import InvalidId
import jwt
from pymongo.asynchronous.database import AsyncDatabase

from app.db import get_db
from app.schemas.user import UserOut
from app.security import decode_access_token

# auto_error=False so a missing header raises OUR 401 with our own message,
# instead of FastAPI's default (less clear) 403.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncDatabase = Depends(get_db),
) -> UserOut:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        object_id = ObjectId(user_id)
    except InvalidId:
        raise HTTPException(status_code=401, detail="Invalid token")

    doc = await db["users"].find_one({"_id": object_id})
    if doc is None:
        raise HTTPException(status_code=401, detail="User no longer exists")

    return UserOut(id=str(doc["_id"]), email=doc["email"], created_at=doc["created_at"])
