"""MLX-LM backend for Recursive Data Cleaner."""

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
        """
        self.model_path = model_path
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.repetition_penalty = repetition_penalty
        self.verbose = verbose

        self._model = None
        self._tokenizer = None
        self._sampler = None
        self._logits_processors = None

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
            formatted_prompt = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            formatted_prompt = prompt

        response = generate(
            self._model,
            self._tokenizer,
            prompt=formatted_prompt,
            max_tokens=self.max_tokens,
            sampler=self._sampler,
            logits_processors=self._logits_processors,
            verbose=self.verbose,
        )

        return response
