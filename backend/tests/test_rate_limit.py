"""
check_rate_limit is a pure function with no DB/AI dependency, so these
are plain sync tests — pytest-asyncio's asyncio_mode=auto only affects
`async def` tests, so sync tests run normally alongside them in the same
session.
"""

import pytest
from fastapi import HTTPException

from app.rate_limit import _MAX_REQUESTS_PER_WINDOW, check_rate_limit


def test_requests_under_the_threshold_are_allowed():
    key = "rate-limit-test-under"
    for _ in range(_MAX_REQUESTS_PER_WINDOW):
        check_rate_limit(key)  # should not raise


def test_requests_over_the_threshold_are_rejected():
    key = "rate-limit-test-over"
    for _ in range(_MAX_REQUESTS_PER_WINDOW):
        check_rate_limit(key)

    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(key)
    assert exc_info.value.status_code == 429


def test_different_keys_have_independent_budgets():
    key_a = "rate-limit-test-a"
    key_b = "rate-limit-test-b"
    for _ in range(_MAX_REQUESTS_PER_WINDOW):
        check_rate_limit(key_a)

    check_rate_limit(key_b)  # a different key's budget is untouched by key_a's usage
