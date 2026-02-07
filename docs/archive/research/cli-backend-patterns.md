# CLI Backend Configuration Patterns Research

Research into how existing LLM CLI tools handle backend/model configuration.

## Tools Analyzed

### 1. llm (Simon Willison's tool)

**Source**: https://llm.datasette.io/

#### API Key Management
- **Stored Keys**: `llm keys set` saves to `keys.json` file
- **CLI Flag**: `--key` option (raw value or alias to stored key)
- **Environment Variables**: Model-specific like `OPENAI_API_KEY`

#### Model Selection
- **Default Model**: `llm models default` sets preferred model (defaults to `gpt-4o-mini`)
- **Per-Command**: `-m/--model` flag

#### Plugin System
Hook-based architecture with key extension points:
- `register_models(register)` - Add new LLM providers
- `register_commands(cli)` - Extend CLI commands
- `register_embedding_models(register)` - Add embedding support

Plugins are standard Python packages, installed via `llm install [plugin-name]`.

#### Configuration Files
- `keys.json` - Stored API keys
- `extra-openai-models.yaml` - Custom OpenAI-compatible endpoints
- `LLM_USER_PATH` env var - Custom config directory

**Key Insight**: The plugin system allows adding any backend without modifying core code. Model switching is seamless via `-m` flag regardless of provider.

---

### 2. Ollama CLI

**Source**: https://github.com/ollama/ollama

#### Model Selection
Direct command specification:
```bash
ollama run llama3.2           # Default variant
ollama run llama3.2:1b        # Specific size
ollama run gemma3:27b         # Specific version
```

#### Model Management
- `ollama pull <model>` - Download models
- `ollama list` - Show local models
- `ollama create mymodel -f ./Modelfile` - Custom models

#### Configuration
- **Modelfile**: Custom model definitions with base model, parameters, system prompts
- No global config file for defaults
- Environment variables for server configuration (`OLLAMA_HOST`, etc.)

**Key Insight**: Extremely simple - model name is always the first argument. No abstraction layers.

---

### 3. OpenAI CLI Tools

**Sources**: OpenAI official docs, Codex CLI, third-party openai-cli

#### Official Pattern (SDK/API)
- **Environment Variable**: `OPENAI_API_KEY` (strongly recommended)
- Auto-detection by SDKs without explicit configuration

#### Codex CLI
- **Config File**: `~/.codex/config.toml`
- **CLI Flags**: `-m/--model` for model override
- **Profile System**: `--profile/-p` for named configurations
- **Auth**: `codex login` (OAuth or API key via stdin)

#### Third-party openai-cli
- **CLI Flag**: `-t/--token <TOKEN>`
- **Environment Variable**: `OPENAI_API_KEY`
- **Endpoint Override**: `OPENAI_API_URL` env var

**Key Insight**: Environment variables are the standard pattern. Config files are optional additions for convenience.

---

### 4. Aider

**Source**: https://aider.chat/docs/

#### Four Equivalent Configuration Methods
1. **Command line switches**: `--model gpt-4o`
2. **YAML config files**: `.aider.conf.yml`
3. **Environment variables**: `AIDER_MODEL`
4. **`.env` files**: Load via `--env-file`

#### API Key Handling
- **Major Providers**: Dedicated flags (`--openai-api-key`, `--anthropic-api-key`)
- **Other Providers**: `--api-key provider=<key>` pattern
- **Environment Variables**: Standard `PROVIDER_API_KEY` format
  ```
  OPENAI_API_KEY=xxx
  ANTHROPIC_API_KEY=xxx
  GEMINI_API_KEY=xxx
  ```

#### Multi-Provider Support
Native support for 20+ providers:
- OpenAI, Anthropic, Gemini, GROQ, DeepSeek
- Ollama, LM Studio (local)
- Azure, Vertex AI, Bedrock (cloud)
- OpenRouter (aggregator)

#### Model Configuration Files
- `.aider.conf.yml` - Main config
- `.aider.model.settings.yml` - Unknown model settings
- `.aider.model.metadata.json` - Context window/cost info

**Key Insight**: Most flexible system. Layered config (CLI > env > file) with provider-specific API key patterns.

---

### 5. Fabric

**Source**: https://github.com/danielmiessler/fabric

#### Setup
Interactive setup command: `fabric --setup`

#### Configuration Storage
- Directory: `~/.config/fabric/`
- Environment variables for additional customization

#### Model Selection
- `--model` flag for default
- `--vendor` flag to specify provider
- `--changeDefaultModel/-d` to update defaults
- Per-pattern env vars: `FABRIC_MODEL_PATTERN_NAME=vendor|model`

#### Provider Support
- Native: OpenAI, Anthropic, Gemini, Ollama, Azure, Bedrock, Vertex AI, LM Studio
- OpenAI-compatible: DeepSeek, Groq, Mistral, Together, GitHub Models, etc.

**Key Insight**: Interactive setup for initial config, then CLI flags for runtime override.

---

## Common Patterns Identified

### 1. API Key Configuration (Priority Order)

Most tools follow this precedence:
1. CLI flag (highest priority)
2. Environment variable
3. Config file
4. Interactive prompt (lowest priority)

**Standard Pattern**:
```
PROVIDER_API_KEY  (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY)
```

### 2. Model Selection

**Universal Pattern**: `-m/--model MODEL_NAME`

Every tool uses this. It's the de facto standard.

### 3. Configuration Files

| Tool | Format | Location |
|------|--------|----------|
| llm | JSON/YAML | `~/.config/io.datasette.llm/` |
| Codex CLI | TOML | `~/.codex/config.toml` |
| Aider | YAML | `.aider.conf.yml` (cwd or home) |
| Fabric | Interactive | `~/.config/fabric/` |

**Trend**: YAML/TOML for human-readable config, JSON for programmatic storage.

### 4. Multi-Backend Support

Three approaches:

1. **Plugin System** (llm): Clean extension, community-driven
2. **Built-in Adapters** (Aider, Fabric): Native support for popular providers
3. **OpenAI-Compatible** (most tools): Treat any provider with OpenAI API compatibility as plug-and-play

### 5. Local vs Remote

Most tools treat local models (Ollama, LM Studio) the same as remote APIs:
- Set endpoint URL
- Specify model name
- No API key needed

---

## Recommendation for Recursive Cleaner

### Simplest Approach That Works

**Phase 1: Environment Variables + CLI Flags**

```python
# User provides backend via CLI
recursive-cleaner clean data.jsonl \
    --model gpt-4o \
    --provider openai

# Or for Ollama
recursive-cleaner clean data.jsonl \
    --model llama3.2 \
    --provider ollama

# API keys from environment
export OPENAI_API_KEY=xxx
export ANTHROPIC_API_KEY=xxx
```

**Phase 2: Config File (Optional)**

```yaml
# ~/.config/recursive-cleaner/config.yaml
default_provider: openai
default_model: gpt-4o

providers:
  openai:
    api_key_env: OPENAI_API_KEY
  anthropic:
    api_key_env: ANTHROPIC_API_KEY
  ollama:
    base_url: http://localhost:11434
```

### Implementation Pattern

```python
# types.py - Keep existing protocol
class LLMBackend(Protocol):
    def generate(self, prompt: str) -> str: ...

# backends/__init__.py - Factory function
def create_backend(
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMBackend:
    """Create backend from provider name."""
    if provider == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY")
        return OpenAIBackend(model=model, api_key=key)
    elif provider == "anthropic":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        return AnthropicBackend(model=model, api_key=key)
    elif provider == "ollama":
        url = base_url or "http://localhost:11434"
        return OllamaBackend(model=model, base_url=url)
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

### CLI Interface (using argparse or click)

```python
@click.command()
@click.argument('file_path')
@click.option('--model', '-m', default='gpt-4o', help='Model name')
@click.option('--provider', '-p', default='openai', help='LLM provider')
@click.option('--api-key', envvar='LLM_API_KEY', help='API key (or use PROVIDER_API_KEY)')
def clean(file_path, model, provider, api_key):
    backend = create_backend(provider, model, api_key)
    cleaner = DataCleaner(llm_backend=backend, file_path=file_path)
    cleaner.run()
```

### Key Decisions

1. **Environment variables for API keys** - Industry standard, secure
2. **`-m/--model` flag** - Universal convention
3. **`-p/--provider` flag** - Clear intent, no ambiguity
4. **Optional config file** - Nice-to-have, not required
5. **No plugin system initially** - Add complexity only if needed

### Provider Priority for Initial Support

1. **OpenAI** - Most common
2. **Anthropic** - Popular alternative
3. **Ollama** - Local models (already have MLX backend)
4. **OpenAI-compatible** - Generic fallback for others

---

## Sources

- [llm documentation](https://llm.datasette.io/)
- [llm plugins](https://llm.datasette.io/en/stable/plugins/index.html)
- [Ollama README](https://github.com/ollama/ollama)
- [Aider configuration](https://aider.chat/docs/config.html)
- [Aider API keys](https://aider.chat/docs/config/api-keys.html)
- [Fabric README](https://github.com/danielmiessler/fabric)
- [OpenAI API key best practices](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety)
- [OpenAI Codex CLI reference](https://developers.openai.com/codex/cli/reference/)
