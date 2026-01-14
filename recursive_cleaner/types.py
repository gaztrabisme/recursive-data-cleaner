"""Type definitions for the recursive cleaner pipeline."""

from typing import Protocol


class LLMBackend(Protocol):
    """Protocol for LLM backend implementations."""

    def generate(self, prompt: str) -> str:
        """Generate a response from the LLM given a prompt."""
        ...
