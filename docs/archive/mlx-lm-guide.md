# MLX-LM Guide for Recursive Data Cleaner

MLX-LM is Apple's official library for running large language models on Apple Silicon using the MLX framework. This guide covers the programmatic Python API for integrating mlx-lm as an LLM backend for the Recursive Data Cleaner.

## Installation

### Via pip (recommended)

```bash
pip install mlx-lm
```

### Via conda

```bash
conda install -c conda-forge mlx-lm
```

### Requirements

- Apple Silicon Mac (M1/M2/M3/M4 series)
- macOS 13.5 or later
- Python 3.9+

## Loading Models

Use the `load()` function to load a model and tokenizer from a local path or HuggingFace repository.

### Basic Usage

```python
from mlx_lm import load

model, tokenizer = load("mlx-community/Mistral-7B-Instruct-v0.3-4bit")
```

### Loading Quantized Models

For models like `lmstudio-community/Qwen3-Next-80B-A3B-Instruct-MLX-4bit`:

```python
from mlx_lm import load

model, tokenizer = load("lmstudio-community/Qwen3-Next-80B-A3B-Instruct-MLX-4bit")
```

### Load Function Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path_or_hf_repo` | `str` | Required | Local path or HuggingFace repository ID |
| `tokenizer_config` | `Dict[str, Any]` | `None` | Custom tokenizer configuration |
| `model_config` | `Dict[str, Any]` | `None` | Custom model configuration |
| `adapter_path` | `str` | `None` | Path to LoRA adapters |
| `lazy` | `bool` | `False` | Lazy loading of model weights |
| `return_config` | `bool` | `False` | Return model config as third element |
| `revision` | `str` | `None` | Branch, tag, or commit hash |

### Example with Options

```python
from mlx_lm import load

model, tokenizer = load(
    "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
    tokenizer_config={"trust_remote_code": True},
    lazy=False
)
```

## Text Generation

### Basic Generation

```python
from mlx_lm import load, generate

model, tokenizer = load("mlx-community/Mistral-7B-Instruct-v0.3-4bit")

prompt = "Explain quantum computing in simple terms."
response = generate(model, tokenizer, prompt=prompt, max_tokens=256)
print(response)
```

### Using Chat Templates

For instruction-tuned models, apply the chat template:

```python
from mlx_lm import load, generate

model, tokenizer = load("mlx-community/Mistral-7B-Instruct-v0.3-4bit")

messages = [{"role": "user", "content": "Write a haiku about programming."}]
prompt = tokenizer.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=False  # Return string, not tokens
)

response = generate(model, tokenizer, prompt=prompt, max_tokens=256)
print(response)
```

### Streaming Generation

For token-by-token output:

```python
from mlx_lm import load, stream_generate

model, tokenizer = load("mlx-community/Mistral-7B-Instruct-v0.3-4bit")

messages = [{"role": "user", "content": "Tell me a story."}]
prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)

for response in stream_generate(model, tokenizer, prompt, max_tokens=512):
    print(response.text, end="", flush=True)
```

## API Reference

### generate()

```python
def generate(
    model: nn.Module,
    tokenizer: PreTrainedTokenizer,
    prompt: Union[str, List[int]],
    verbose: bool = False,
    **kwargs
) -> str
```

Returns the complete generated text as a string.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `nn.Module` | Required | The loaded language model |
| `tokenizer` | `PreTrainedTokenizer` | Required | The tokenizer |
| `prompt` | `str` or `List[int]` | Required | Input text or token IDs |
| `verbose` | `bool` | `False` | Print tokens and timing info |
| `**kwargs` | - | - | Passed to `stream_generate()` |

### stream_generate()

```python
def stream_generate(
    model: nn.Module,
    tokenizer: PreTrainedTokenizer,
    prompt: Union[str, mx.array, List[int]],
    max_tokens: int = 256,
    draft_model: Optional[nn.Module] = None,
    **kwargs
) -> Generator[GenerationResponse, None, None]
```

Yields `GenerationResponse` objects with incremental text.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `nn.Module` | Required | The loaded language model |
| `tokenizer` | `PreTrainedTokenizer` | Required | The tokenizer |
| `prompt` | `str`, `mx.array`, or `List[int]` | Required | Input prompt |
| `max_tokens` | `int` | `256` | Maximum tokens to generate |
| `draft_model` | `nn.Module` | `None` | Draft model for speculative decoding |
| `sampler` | `Callable` | `None` | Custom sampling function |
| `logits_processors` | `List[Callable]` | `None` | Logits processing functions |
| `max_kv_size` | `int` | `None` | Maximum KV cache size |
| `prefill_step_size` | `int` | `2048` | Prompt processing chunk size |

### GenerationResponse

The response object yielded by `stream_generate()`:

| Attribute | Type | Description |
|-----------|------|-------------|
| `text` | `str` | Generated text so far |
| `token` | `int` | Current token ID |
| `logprobs` | `mx.array` | Log probabilities |
| `prompt_tokens` | `int` | Number of prompt tokens |
| `generation_tokens` | `int` | Number of generated tokens |
| `prompt_tps` | `float` | Prompt processing tokens/sec |
| `generation_tps` | `float` | Generation tokens/sec |
| `peak_memory` | `float` | Peak memory usage |
| `finish_reason` | `str` | Why generation stopped |

## Sampling Configuration

### make_sampler()

Create a sampler with temperature and other controls:

```python
from mlx_lm.sample_utils import make_sampler

sampler = make_sampler(
    temp=0.7,      # Temperature (0 = greedy/argmax)
    top_p=0.9,     # Nucleus sampling threshold
    top_k=40,      # Top-k sampling
    min_p=0.0,     # Minimum probability threshold
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `temp` | `float` | `0.0` | Temperature. 0 = deterministic (argmax) |
| `top_p` | `float` | `0.0` | Nucleus sampling. Higher = more diverse |
| `top_k` | `int` | `0` | Limit to top k tokens. 0 = disabled |
| `min_p` | `float` | `0.0` | Min probability relative to top token |
| `min_tokens_to_keep` | `int` | `1` | Minimum tokens after filtering |
| `xtc_probability` | `float` | `0.0` | XTC sampling probability |
| `xtc_threshold` | `float` | `0.0` | XTC threshold |

### make_logits_processors()

Add repetition penalty and logit bias:

```python
from mlx_lm.sample_utils import make_logits_processors

processors = make_logits_processors(
    repetition_penalty=1.1,      # Penalize repeated tokens
    repetition_context_size=20,  # Look back this many tokens
    logit_bias={123: -100},      # Bias specific tokens
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `logit_bias` | `Dict[int, float]` | `None` | Token ID to bias value mapping |
| `repetition_penalty` | `float` | `None` | Penalty for repeated tokens |
| `repetition_context_size` | `int` | `20` | Tokens to check for repetition |

### Using Samplers with Generate

```python
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler, make_logits_processors

model, tokenizer = load("mlx-community/Mistral-7B-Instruct-v0.3-4bit")

sampler = make_sampler(temp=0.7, top_p=0.9)
processors = make_logits_processors(repetition_penalty=1.1)

response = generate(
    model,
    tokenizer,
    prompt="Write a poem about coding.",
    max_tokens=256,
    sampler=sampler,
    logits_processors=processors
)
```

## Example Integration

Here is an example LLM backend class for the Recursive Data Cleaner:

```python
"""
MLX-LM backend for Recursive Data Cleaner.

Example usage:
    from mlx_backend import MLXBackend
    from recursive_cleaner import DataCleaner

    backend = MLXBackend("mlx-community/Mistral-7B-Instruct-v0.3-4bit")
    cleaner = DataCleaner(
        llm_backend=backend,
        file_path="data.jsonl",
        instructions="Clean and normalize the data"
    )
    cleaner.run()
"""

from typing import Protocol
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler, make_logits_processors


class LLMBackend(Protocol):
    """Protocol for LLM backends."""
    def generate(self, prompt: str) -> str: ...


class MLXBackend:
    """MLX-LM backend implementation."""

    def __init__(
        self,
        model_path: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repetition_penalty: float = 1.1,
        use_chat_template: bool = True,
    ):
        """
        Initialize the MLX backend.

        Args:
            model_path: HuggingFace repo ID or local path to model
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0 = deterministic)
            top_p: Nucleus sampling threshold
            repetition_penalty: Penalty for repeated tokens
            use_chat_template: Apply chat template to prompts
        """
        self.model, self.tokenizer = load(model_path)
        self.max_tokens = max_tokens
        self.use_chat_template = use_chat_template

        # Create sampler and processors
        self.sampler = make_sampler(temp=temperature, top_p=top_p)
        self.logits_processors = make_logits_processors(
            repetition_penalty=repetition_penalty
        )

    def generate(self, prompt: str) -> str:
        """
        Generate text from a prompt.

        Args:
            prompt: The input prompt

        Returns:
            Generated text response
        """
        # Apply chat template if enabled
        if self.use_chat_template:
            messages = [{"role": "user", "content": prompt}]
            formatted_prompt = self.tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=False
            )
        else:
            formatted_prompt = prompt

        # Generate response
        response = generate(
            self.model,
            self.tokenizer,
            prompt=formatted_prompt,
            max_tokens=self.max_tokens,
            sampler=self.sampler,
            logits_processors=self.logits_processors,
        )

        return response


# Convenience function for quick setup
def create_mlx_backend(
    model: str = "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
    **kwargs
) -> MLXBackend:
    """
    Create an MLX backend with sensible defaults.

    Args:
        model: Model path or HuggingFace repo ID
        **kwargs: Additional arguments for MLXBackend

    Returns:
        Configured MLXBackend instance
    """
    return MLXBackend(model, **kwargs)
```

## Notes

### Memory Management

- MLX uses unified memory on Apple Silicon, sharing RAM between CPU and GPU
- For large models, consider using `--max-kv-size` to limit KV cache growth
- Quantized models (4-bit, 8-bit) significantly reduce memory requirements

### Model Selection

- The `mlx-community` organization on HuggingFace hosts pre-converted models
- Models from `lmstudio-community` are also MLX-compatible
- Look for models with `-MLX-4bit` or `-MLX-8bit` suffixes for quantized versions

### Performance Tips

1. **Use quantized models** - 4-bit models offer good quality with lower memory
2. **Batch prompts when possible** - Use `batch_generate()` for multiple prompts
3. **Enable prompt caching** - For multi-turn conversations, cache the KV state
4. **Adjust prefill_step_size** - Larger values can speed up prompt processing

### Common Models for Data Cleaning Tasks

| Model | Size | Good For |
|-------|------|----------|
| `mlx-community/Mistral-7B-Instruct-v0.3-4bit` | ~4GB | General tasks |
| `mlx-community/Llama-3.2-3B-Instruct-4bit` | ~2GB | Quick iterations |
| `mlx-community/Qwen2.5-7B-Instruct-4bit` | ~4GB | Code generation |
| `mlx-community/Qwen2.5-32B-Instruct-4bit` | ~18GB | Complex reasoning |

### Differences from Other Backends

- MLX runs locally, no API keys needed
- First run downloads the model (can take time)
- Inference speed depends on your Mac's hardware
- No rate limits or usage costs

### Troubleshooting

**Model download issues:**
```python
# Specify a revision if latest fails
model, tokenizer = load("model-name", revision="main")
```

**Memory errors:**
- Use a smaller/more quantized model
- Reduce `max_tokens`
- Close other applications

**Slow generation:**
- Ensure you are using a quantized model
- Check Activity Monitor for thermal throttling
- Reduce `max_tokens` if you do not need long outputs
