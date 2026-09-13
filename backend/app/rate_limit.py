"""
A plain in-memory rate limiter, not a distributed one — this app runs as
one process, so that's the right amount of complexity for what it's
protecting: Gemini's free-tier rate limit (~15 requests/minute on the
current model), not general API abuse. Without this, a buggy client
retry loop or a double-click could burn through that quota in seconds
and turn every subsequent request into a real 429 from Gemini itself.

Not applied to /auth/* — that's a different concern (credential brute
force), needing a different mechanism, and is a disclosed gap rather
than something silently left unguarded — see the README.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException

_WINDOW_SECONDS = 60
_MAX_REQUESTS_PER_WINDOW = 10  # comfortably under Gemini's free-tier RPM

_request_log: dict[str, deque] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    """Raises 429 if `key` has made too many requests in the last
    _WINDOW_SECONDS. Called directly inside a route (after current_user is
    already resolved, so the key can be the user id) rather than wired up
    as its own Depends() — simpler to read for what's a small safety net,
    not a general-purpose piece of app plumbing."""
    now = time.monotonic()
    log = _request_log[key]
    while log and now - log[0] > _WINDOW_SECONDS:
        log.popleft()
    if len(log) >= _MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(status_code=429, detail="Too many requests — please wait a moment and try again.")
    log.append(now)
