"""MLX-LM backend for Recursive Data Cleaner."""

import time

from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler, make_logits_processors


class MLXBackend:
    """
    MLX-LM backend implementation for Apple Silicon.

    Conforms to the LLMBackend protocol.
    """

    def __init__(
        self,
        model_path: str = "lmstudio-community/Qwen3-Next-80B-A3B-Instruct-MLX-4bit",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repetition_penalty: float = 1.1,
        verbose: bool = False,
        enable_thinking: bool = True,
    ):
        """
        Initialize the MLX backend.

        Args:
            model_path: HuggingFace model path or local path
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0 = deterministic)
            top_p: Nucleus sampling threshold
            repetition_penalty: Penalty for repeated tokens
            verbose: Whether to print loading info
            enable_thinking: Whether to allow model thinking (Qwen3 <think> blocks).
                Set False for data cleaning tasks to avoid wasting tokens on reasoning.
        """
        self.model_path = model_path
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.repetition_penalty = repetition_penalty
        self.verbose = verbose
        self.enable_thinking = enable_thinking

        self._model = None
        self._tokenizer = None
        self._sampler = None
        self._logits_processors = None

        # Per-call stats for benchmarking
        self._last_prompt_tokens = 0
        self._last_response_tokens = 0
        self._last_generation_time_s = 0.0

        # Cumulative stats across all calls
        self._total_prompt_tokens = 0
        self._total_response_tokens = 0
        self._total_generation_time_s = 0.0
        self._call_count = 0

    def _ensure_loaded(self):
        """Lazy load the model on first use."""
        if self._model is None:
            if self.verbose:
                print(f"Loading model: {self.model_path}")
            self._model, self._tokenizer = load(self.model_path)

            # Create sampler and processors
            self._sampler = make_sampler(temp=self.temperature, top_p=self.top_p)
            self._logits_processors = make_logits_processors(
                repetition_penalty=self.repetition_penalty
            )

            if self.verbose:
                print("Model loaded successfully")

    def download(self) -> float:
        """Download model files to HF cache without loading into memory.

        Returns:
            Download time in seconds (0 if already cached).
        """
        from huggingface_hub import snapshot_download

        t0 = time.perf_counter()
        snapshot_download(self.model_path)
        return time.perf_counter() - t0

    def load_model(self) -> float:
        """Load model into memory (assumes already downloaded).

        Returns:
            Load time in seconds.
        """
        t0 = time.perf_counter()
        self._ensure_loaded()
        return time.perf_counter() - t0

    def generate(self, prompt: str) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: The input prompt

        Returns:
            The generated text response
        """
        self._ensure_loaded()

        # Apply chat template if available (for instruction-tuned models)
        if hasattr(self._tokenizer, 'apply_chat_template'):
            messages = [{"role": "user", "content": prompt}]
            template_kwargs = dict(
                tokenize=False,
                add_generation_prompt=True,
            )
            if not self.enable_thinking:
                template_kwargs["enable_thinking"] = False
            formatted_prompt = self._tokenizer.apply_chat_template(
                messages,
                **template_kwargs,
            )
        else:
            formatted_prompt = prompt

        t0 = time.perf_counter()
        response = generate(
            self._model,
            self._tokenizer,
            prompt=formatted_prompt,
            max_tokens=self.max_tokens,
            sampler=self._sampler,
            logits_processors=self._logits_processors,
            verbose=self.verbose,
        )
        gen_time = time.perf_counter() - t0

        # Count tokens and track timing
        try:
            self._last_prompt_tokens = len(self._tokenizer.encode(formatted_prompt))
            self._last_response_tokens = len(self._tokenizer.encode(response))
        except Exception:
            self._last_prompt_tokens = 0
            self._last_response_tokens = 0

        self._last_generation_time_s = gen_time

        # Accumulate
        self._total_prompt_tokens += self._last_prompt_tokens
        self._total_response_tokens += self._last_response_tokens
        self._total_generation_time_s += gen_time
        self._call_count += 1

        return response

    @property
    def last_generation_stats(self) -> dict | None:
        """Stats from the most recent generation call."""
        if self._call_count == 0:
            return None
        decode_tok_s = (
            self._last_response_tokens / self._last_generation_time_s
            if self._last_generation_time_s > 0 else 0
        )
        return {
            "prompt_tokens": self._last_prompt_tokens,
            "response_tokens": self._last_response_tokens,
            "generation_time_s": round(self._last_generation_time_s, 3),
            "decode_tok_per_s": round(decode_tok_s, 1),
        }

    @property
    def cumulative_stats(self) -> dict:
        """Cumulative stats across all generation calls."""
        avg_decode = (
            self._total_response_tokens / self._total_generation_time_s
            if self._total_generation_time_s > 0 else 0
        )
        return {
            "call_count": self._call_count,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_response_tokens": self._total_response_tokens,
            "total_generation_time_s": round(self._total_generation_time_s, 3),
            "avg_decode_tok_per_s": round(avg_decode, 1),
        }
