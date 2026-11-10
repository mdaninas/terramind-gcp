"""Shared wall-clock and physical-call limits, including bounded transient retries."""

import time
from collections.abc import Callable
from typing import TypeVar

from terramind.llm.diagnostics import AdvisoryReason, AdvisoryUnavailable

T = TypeVar("T")


def failure_reason(error: Exception) -> AdvisoryReason:
    status = getattr(error, "code", None)
    if isinstance(status, int):
        if status == 429:
            return AdvisoryReason.RATE_LIMIT
        if status in {408, 504}:
            return AdvisoryReason.TIMEOUT
        if status in {400, 401, 403, 404, 422}:
            return AdvisoryReason.REJECTED
    if isinstance(error, TimeoutError) or type(error).__name__ in {
        "TimeoutException",
        "ReadTimeout",
        "ConnectTimeout",
        "WriteTimeout",
        "PoolTimeout",
        "DeadlineExceeded",
    }:
        return AdvisoryReason.TIMEOUT
    return AdvisoryReason.DEPENDENCY


class DependencyUnavailable(AdvisoryUnavailable):
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
                raise DependencyUnavailable(
                    "External call budget exhausted",
                    reason=AdvisoryReason.DEADLINE if remaining <= 0 else AdvisoryReason.CALL_LIMIT,
                )
            self.calls += 1
            try:
                result = operation(min(remaining, self.per_call))
                if time.monotonic() > self.deadline:
                    raise DependencyUnavailable(
                        "External deadline exceeded", reason=AdvisoryReason.DEADLINE
                    )
                return result
            except Exception as error:
                if isinstance(error, AdvisoryUnavailable):
                    raise
                reason = (
                    AdvisoryReason.DEADLINE
                    if time.monotonic() >= self.deadline
                    else failure_reason(error)
                )
                if attempt == 2 or not transient(error):
                    raise DependencyUnavailable(
                        "External dependency unavailable", reason=reason
                    ) from None
                delay = 0.2 * 2**attempt
                if self.deadline - time.monotonic() <= delay:
                    raise DependencyUnavailable(
                        "External call budget exhausted", reason=AdvisoryReason.DEADLINE
                    ) from None
                time.sleep(delay)
        raise DependencyUnavailable("External dependency unavailable")
