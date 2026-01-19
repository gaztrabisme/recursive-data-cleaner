"""OpenAI-compatible backend for Recursive Data Cleaner."""

import os


class OpenAIBackend:
    """
    OpenAI-compatible backend implementation.

    Works with OpenAI API, LM Studio, Ollama, and other OpenAI-compatible servers.
    Conforms to the LLMBackend protocol.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """
        Initialize the OpenAI backend.

        Args:
            model: Model name (e.g., "gpt-4o", "gpt-3.5-turbo")
            api_key: API key (defaults to OPENAI_API_KEY env var, or "not-needed" for local)
            base_url: API base URL (defaults to OpenAI's API)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
        """
        try:
            import openai
        except ImportError:
            raise ImportError(
                "OpenAI SDK not installed. Install with: pip install openai"
            )

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Resolve API key: explicit > env var > "not-needed" for local servers
        if api_key is not None:
            resolved_key = api_key
        else:
            resolved_key = os.environ.get("OPENAI_API_KEY", "not-needed")

        # Create client
        self._client = openai.OpenAI(
            api_key=resolved_key,
            base_url=base_url,
        )

    def generate(self, prompt: str) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: The input prompt

        Returns:
            The generated text response
        """
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return response.choices[0].message.content or ""
