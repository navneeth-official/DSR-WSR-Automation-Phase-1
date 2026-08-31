"""Sliding-window rate limiter for WSR LLM calls."""

from __future__ import annotations

import threading
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar

from app.config import get_settings

_wsr_rate_limit_enabled: ContextVar[bool] = ContextVar(
    "wsr_rate_limit_enabled",
    default=False,
)

_limiter_lock = threading.Lock()
_limiter: SlidingWindowRateLimiter | None = None


class SlidingWindowRateLimiter:
    """Allow at most ``max_calls`` within a rolling ``window_seconds`` window."""

    def __init__(self, max_calls: int, window_seconds: float) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be at least 1")
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                cutoff = now - self.window_seconds
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(now)
                    return

                sleep_for = self._timestamps[0] + self.window_seconds - now

            time.sleep(max(sleep_for, 0.05))


def _get_limiter() -> SlidingWindowRateLimiter:
    global _limiter
    with _limiter_lock:
        if _limiter is None:
            settings = get_settings()
            _limiter = SlidingWindowRateLimiter(
                max_calls=settings.wsr_llm_max_calls_per_minute,
                window_seconds=60.0,
            )
        return _limiter


def is_wsr_rate_limit_enabled() -> bool:
    return _wsr_rate_limit_enabled.get()


def maybe_acquire_wsr_rate_limit() -> None:
    """Wait if WSR generation has hit the per-minute LLM call cap."""
    if _wsr_rate_limit_enabled.get():
        _get_limiter().acquire()


@contextmanager
def wsr_llm_rate_limit():
    """Enable WSR LLM rate limiting for the current call stack."""
    token = _wsr_rate_limit_enabled.set(True)
    try:
        yield
    finally:
        _wsr_rate_limit_enabled.reset(token)
