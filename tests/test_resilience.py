"""Tests for backend resilience primitives and semantic cache."""
from __future__ import annotations

import time
import pytest
from backend.resilience import (
    CBState,
    CircuitBreaker,
    ExponentialBackoffRetry,
    TimeoutManager,
    Bulkhead,
    get_circuit_breaker,
    get_all_circuit_breaker_metrics,
)
from backend.semantic_cache import SemanticCache


# ── CircuitBreaker ─────────────────────────────────────────────────────────────

class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker("test-init", min_calls=2)
        assert cb.state == CBState.CLOSED

    def test_success_stays_closed(self):
        cb = CircuitBreaker("test-success", min_calls=2)
        for _ in range(5):
            cb.call(lambda: "ok")
        assert cb.state == CBState.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker("test-open", failure_threshold=0.5, min_calls=2)
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
            except RuntimeError:
                pass
        assert cb.state == CBState.OPEN

    def test_open_uses_fallback(self):
        cb = CircuitBreaker("test-fallback", failure_threshold=0.5, min_calls=2)
        # Force open
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
            except RuntimeError:
                pass
        result = cb.call(lambda: "should-not-run", fallback=lambda: "fallback-value")
        assert result == "fallback-value"

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker("test-halfopen", failure_threshold=0.5, min_calls=2, recovery_timeout=0.1)
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
            except RuntimeError:
                pass
        assert cb.state == CBState.OPEN
        time.sleep(0.3)
        assert cb.state == CBState.HALF_OPEN

    def test_recovers_to_closed_on_success(self):
        cb = CircuitBreaker("test-recover", failure_threshold=0.5, min_calls=2, recovery_timeout=0.1)
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
            except RuntimeError:
                pass
        time.sleep(0.3)
        cb.call(lambda: "ok")
        assert cb.state == CBState.CLOSED

    def test_metrics_structure(self):
        cb = CircuitBreaker("test-metrics", min_calls=2)
        cb.call(lambda: "ok")
        m = cb.get_metrics()
        assert m["name"] == "test-metrics"
        assert m["state"] == "closed"
        assert m["total_calls"] == 1
        assert m["successes"] == 1
        assert m["failures"] == 0

    def test_get_circuit_breaker_singleton(self):
        cb1 = get_circuit_breaker("singleton-test")
        cb2 = get_circuit_breaker("singleton-test")
        assert cb1 is cb2


# ── ExponentialBackoffRetry ────────────────────────────────────────────────────

class TestExponentialBackoffRetry:
    def test_succeeds_on_first_try(self):
        retry = ExponentialBackoffRetry(max_attempts=3, base_delay=0.01)
        calls = []
        result = retry.execute(lambda: calls.append(1) or "done")
        assert result == "done"
        assert len(calls) == 1

    def test_retries_on_failure(self):
        retry = ExponentialBackoffRetry(max_attempts=3, base_delay=0.01, jitter=False)
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("not yet")
            return "ok"

        result = retry.execute(flaky)
        assert result == "ok"
        assert len(calls) == 3

    def test_raises_after_max_attempts(self):
        retry = ExponentialBackoffRetry(max_attempts=2, base_delay=0.01, jitter=False)
        with pytest.raises(ValueError, match="always fails"):
            retry.execute(lambda: (_ for _ in ()).throw(ValueError("always fails")))


# ── TimeoutManager ─────────────────────────────────────────────────────────────

class TestTimeoutManager:
    def test_returns_result_within_timeout(self):
        result = TimeoutManager.with_timeout(lambda: "fast", timeout_seconds=1.0)
        assert result == "fast"

    def test_raises_on_timeout(self):
        with pytest.raises(TimeoutError):
            TimeoutManager.with_timeout(lambda: time.sleep(10), timeout_seconds=0.3)

    def test_uses_fallback_on_timeout(self):
        result = TimeoutManager.with_timeout(
            lambda: time.sleep(10),
            timeout_seconds=0.3,
            fallback=lambda: "fallback",
        )
        assert result == "fallback"


# ── Bulkhead ───────────────────────────────────────────────────────────────────

class TestBulkhead:
    def test_allows_calls_within_limit(self):
        bh = Bulkhead("test-bh", max_concurrent=2, queue_size=5)
        result = bh.call(lambda: "ok")
        assert result == "ok"
        assert bh.rejected_count == 0


# ── SemanticCache ──────────────────────────────────────────────────────────────

class TestSemanticCache:
    def _make_emb(self, val: float, size: int = 8) -> list:
        import math
        v = [val] * size
        norm = math.sqrt(sum(x * x for x in v))
        return [x / norm for x in v]

    def test_miss_on_empty_cache(self):
        cache = SemanticCache(similarity_threshold=0.95)
        result = cache.get(self._make_emb(0.5))
        assert result is None

    def test_hit_on_identical_embedding(self):
        cache = SemanticCache(similarity_threshold=0.95)
        emb = self._make_emb(0.7)
        cache.put(emb, "cached response")
        result = cache.get(emb)
        assert result == "cached response"

    def test_miss_on_dissimilar_embedding(self):
        cache = SemanticCache(similarity_threshold=0.95)
        emb_a = self._make_emb(1.0)
        emb_b = [0.0] * 7 + [1.0]  # orthogonal
        cache.put(emb_a, "response a")
        result = cache.get(emb_b)
        assert result is None

    def test_ttl_eviction(self):
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=0.1)
        emb = self._make_emb(0.5)
        cache.put(emb, "will expire")
        time.sleep(0.4)
        result = cache.get(emb)
        assert result is None

    def test_clear(self):
        cache = SemanticCache(similarity_threshold=0.95)
        emb = self._make_emb(0.5)
        cache.put(emb, "data")
        cache.clear()
        assert cache.get(emb) is None

    def test_stats_tracks_hits_and_misses(self):
        cache = SemanticCache(similarity_threshold=0.95)
        emb = self._make_emb(0.5)
        cache.get(emb)  # miss
        cache.put(emb, "data")
        cache.get(emb)  # hit
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_max_entries_eviction(self):
        cache = SemanticCache(similarity_threshold=0.99, max_entries=3)
        for i in range(5):
            cache.put(self._make_emb(float(i) / 10 + 0.01), f"response-{i}")
        assert len(cache._entries) <= 3
