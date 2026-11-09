"""Shared wall-clock and physical-call limits, including bounded transient retries."""

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class DependencyUnavailable(RuntimeError):
    """A safe external-dependency error without provider details."""


class CallBudget:
    def __init__(self, seconds: float = 20, max_calls: int = 20, per_call: float = 8):
        if not 0 < seconds <= 300 or not 1 <= max_calls <= 500 or not 0 < per_call <= 30:
            raise ValueError("Invalid external call budget")
        self.deadline = time.monotonic() + seconds
        self.max_calls = max_calls
        self.per_call = per_call
        self.calls = 0

    def run(self, operation: Callable[[float], T], *, transient: Callable[[Exception], bool]) -> T:
        for attempt in range(3):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or self.calls >= self.max_calls:
                raise DependencyUnavailable("External call budget exhausted")
            self.calls += 1
            try:
                result = operation(min(remaining, self.per_call))
                if time.monotonic() > self.deadline:
                    raise DependencyUnavailable("External deadline exceeded")
                return result
            except Exception as error:
                if attempt == 2 or not transient(error):
                    raise DependencyUnavailable("External dependency unavailable") from None
                delay = 0.2 * 2**attempt
                if self.deadline - time.monotonic() <= delay:
                    raise DependencyUnavailable("External call budget exhausted") from None
                time.sleep(delay)
        raise DependencyUnavailable("External dependency unavailable")
