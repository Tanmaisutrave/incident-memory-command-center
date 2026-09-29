"""Shared pytest fixtures for all test modules.

Resets global mutable singletons before each test so tests are fully isolated
regardless of run order.
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_security_state():
    """Clear rate-limiter buckets and call counters before every test."""
    from app.security import _rate_limiter, call_counter
    import threading

    # Clear all per-IP buckets
    with _rate_limiter._lock:
        _rate_limiter._buckets.clear()

    # Reset call counters
    with call_counter._lock:
        call_counter._daily = 0
        call_counter._monthly = 0
        call_counter._day = 0
        call_counter._month = 0

    yield
