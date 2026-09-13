"""
Password hashing (bcrypt) and JWT issuance/verification (PyJWT).

Deliberately not python-jose/passlib — both have gone quiet on
maintenance. PyJWT and bcrypt are small, current, and each do exactly
one job.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> tuple[str, datetime]:
    """Returns (token, expires_at) so the caller can include expiry in the response."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expires_at}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> str:
    """Returns the user id from the 'sub' claim. Raises jwt exceptions (caught in app/deps.py)
    on an invalid signature, malformed token, or expired token — callers must handle those."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    return payload["sub"]
