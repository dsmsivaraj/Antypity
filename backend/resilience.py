"""Resilience primitives: circuit breaker, retry with backoff, timeout, bulkhead."""
from __future__ import annotations

import asyncio
import functools
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

_logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ── Circuit Breaker ────────────────────────────────────────────────────────────

class CBState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerStats:
    total_calls: int = 0
    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[float] = None
    state_transitions: int = 0


class CircuitBreaker:
    """3-state circuit breaker (CLOSED → OPEN → HALF_OPEN → CLOSED).

    failure_threshold: fraction of calls that must fail to open the circuit.
    recovery_timeout: seconds in OPEN before moving to HALF_OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: float = 0.5,
        recovery_timeout: float = 60.0,
        min_calls: int = 5,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.min_calls = min_calls
        self._state = CBState.CLOSED
        self._stats = CircuitBreakerStats()
        self._lock = threading.Lock()

    @property
    def state(self) -> CBState:
        with self._lock:
            return self._evaluate_state()

    def _evaluate_state(self) -> CBState:
        if self._state == CBState.OPEN:
            if (
                self._stats.last_failure_time is not None
                and time.monotonic() - self._stats.last_failure_time >= self.recovery_timeout
            ):
                self._state = CBState.HALF_OPEN
                self._stats.state_transitions += 1
                _logger.info("CircuitBreaker[%s] → HALF_OPEN", self.name)
        return self._state

    def call(self, fn: Callable, *args, fallback: Optional[Callable] = None, **kwargs):
        with self._lock:
            state = self._evaluate_state()
            if state == CBState.OPEN:
                _logger.warning("CircuitBreaker[%s] OPEN — rejecting call", self.name)
                if fallback:
                    return fallback(*args, **kwargs)
                raise RuntimeError(f"CircuitBreaker[{self.name}] is OPEN")

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            if fallback:
                return fallback(*args, **kwargs)
            raise exc

    def _on_success(self) -> None:
        with self._lock:
            self._stats.successes += 1
            self._stats.total_calls += 1
            if self._state == CBState.HALF_OPEN:
                self._state = CBState.CLOSED
                self._stats.failures = 0
                self._stats.state_transitions += 1
                _logger.info("CircuitBreaker[%s] → CLOSED (recovered)", self.name)

    def _on_failure(self) -> None:
        with self._lock:
            self._stats.failures += 1
            self._stats.total_calls += 1
            self._stats.last_failure_time = time.monotonic()

            if self._state == CBState.HALF_OPEN:
                self._state = CBState.OPEN
                self._stats.state_transitions += 1
                _logger.warning("CircuitBreaker[%s] → OPEN (probe failed)", self.name)
                return

            if self._stats.total_calls >= self.min_calls:
                failure_rate = self._stats.failures / self._stats.total_calls
                if failure_rate >= self.failure_threshold and self._state == CBState.CLOSED:
                    self._state = CBState.OPEN
                    self._stats.state_transitions += 1
                    _logger.warning(
                        "CircuitBreaker[%s] → OPEN (failure_rate=%.0f%%)",
                        self.name,
                        failure_rate * 100,
                    )

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            state = self._evaluate_state()
            return {
                "name": self.name,
                "state": state.value,
                "total_calls": self._stats.total_calls,
                "failures": self._stats.failures,
                "successes": self._stats.successes,
                "failure_rate": (
                    round(self._stats.failures / self._stats.total_calls, 3)
                    if self._stats.total_calls else 0.0
                ),
                "state_transitions": self._stats.state_transitions,
            }


# ── Exponential Backoff Retry ──────────────────────────────────────────────────

class ExponentialBackoffRetry:
    """Retries a callable with exponential backoff and optional jitter."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (Exception,),
    ) -> None:
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def execute(self, fn: Callable, *args, **kwargs):
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return fn(*args, **kwargs)
            except self.retryable_exceptions as exc:
                last_exc = exc
                if attempt == self.max_attempts:
                    break
                delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                if self.jitter:
                    delay *= (0.5 + random.random() * 0.5)
                _logger.warning(
                    "Retry %d/%d failed (%s), backing off %.2fs",
                    attempt, self.max_attempts, exc, delay,
                )
                time.sleep(delay)
        raise last_exc  # type: ignore[misc]


# ── Timeout Manager ────────────────────────────────────────────────────────────

class TimeoutManager:
    """Runs a callable with a wall-clock timeout (sync, thread-based)."""

    @staticmethod
    def with_timeout(
        fn: Callable,
        timeout_seconds: float,
        fallback: Optional[Callable] = None,
        *args,
        **kwargs,
    ):
        result_holder: list = []
        exc_holder: list = []

        def _run():
            try:
                result_holder.append(fn(*args, **kwargs))
            except Exception as exc:
                exc_holder.append(exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout_seconds)
        if t.is_alive():
            _logger.warning("TimeoutManager: call timed out after %.1fs", timeout_seconds)
            if fallback:
                return fallback(*args, **kwargs)
            raise TimeoutError(f"Call timed out after {timeout_seconds}s")
        if exc_holder:
            raise exc_holder[0]
        return result_holder[0]


# ── Bulkhead ───────────────────────────────────────────────────────────────────

class Bulkhead:
    """Limits concurrent calls and queued calls (semaphore-based)."""

    def __init__(self, name: str, max_concurrent: int = 10, queue_size: int = 100) -> None:
        self.name = name
        self._semaphore = threading.Semaphore(max_concurrent + queue_size)
        self._active_semaphore = threading.Semaphore(max_concurrent)
        self._rejected = 0

    def call(self, fn: Callable, *args, **kwargs):
        if not self._semaphore.acquire(blocking=False):
            self._rejected += 1
            _logger.warning("Bulkhead[%s] rejected call (queue full)", self.name)
            raise RuntimeError(f"Bulkhead[{self.name}] at capacity")
        try:
            self._active_semaphore.acquire()
            try:
                return fn(*args, **kwargs)
            finally:
                self._active_semaphore.release()
        finally:
            self._semaphore.release()

    @property
    def rejected_count(self) -> int:
        return self._rejected


# ── Registry ───────────────────────────────────────────────────────────────────

_circuit_breakers: Dict[str, CircuitBreaker] = {}
_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: float = 0.5,
    recovery_timeout: float = 60.0,
    min_calls: int = 5,
) -> CircuitBreaker:
    with _lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                min_calls=min_calls,
            )
        return _circuit_breakers[name]


def get_all_circuit_breaker_metrics() -> list[Dict[str, Any]]:
    with _lock:
        return [cb.get_metrics() for cb in _circuit_breakers.values()]
