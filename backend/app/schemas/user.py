"""
Three different shapes for "a user", on purpose:

- UserSignupIn / UserLoginIn: the ONLY fields a client is allowed to send.
  extra="forbid" means an unexpected field (e.g. a client trying to set
  "isAdmin" or "id") gets a 422, not silently ignored.
- UserOut: the ONLY fields a client is allowed to receive. There is no
  password_hash field on this model, so it is structurally impossible for
  a route with response_model=UserOut to leak it, even if the handler
  code has a bug and passes the full DB document around internally.
- The actual MongoDB document (email, password_hash, created_at, plus
  Mongo's _id) is never modeled as a Pydantic class here — we're not
  using an ODM, so it's just a plain dict, built and read directly in
  app/routers/auth.py. Keeping it a dict (rather than a fourth "UserDB"
  Pydantic model) avoids a redundant schema that would only exist to
  mirror the other three.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserSignupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime


class TokenOut(BaseModel):
    user: UserOut
    token: str
    expires_at: datetime
