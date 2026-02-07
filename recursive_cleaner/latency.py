"""Latency tracking for LLM calls."""

import time

from tenacity import retry, stop_after_attempt, wait_exponential

from .types import LLMBackend


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def call_llm(backend: LLMBackend, prompt: str) -> str:
    """Call LLM with retry logic."""
    return backend.generate(prompt)


class LatencyTracker:
    """Track timing statistics for LLM calls."""

    def __init__(self):
        self.call_count: int = 0
        self.total_ms: float = 0.0
        self.min_ms: float = float("inf")
        self.max_ms: float = 0.0

    def timed_call(self, backend: LLMBackend, prompt: str) -> tuple[str, float]:
        """
        Call LLM with timing. Returns (response, elapsed_ms).
        """
        start = time.perf_counter()
        response = call_llm(backend, prompt)
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.call_count += 1
        self.total_ms += elapsed_ms
        self.min_ms = min(self.min_ms, elapsed_ms)
        self.max_ms = max(self.max_ms, elapsed_ms)

        return response, elapsed_ms

    def summary(self) -> dict:
        """Get summary of latency stats with avg calculation."""
        stats = {
            "call_count": self.call_count,
            "total_ms": round(self.total_ms, 2),
            "min_ms": round(self.min_ms, 2) if self.call_count > 0 else 0.0,
            "max_ms": round(self.max_ms, 2),
        }
        if self.call_count > 0:
            stats["avg_ms"] = round(self.total_ms / self.call_count, 2)
        else:
            stats["avg_ms"] = 0.0
            stats["min_ms"] = 0.0
        return stats
