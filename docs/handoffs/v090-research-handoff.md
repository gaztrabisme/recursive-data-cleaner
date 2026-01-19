# Research Handoff - v0.9.0 CLI Tool

## Recommendation

Build a minimal argparse-based CLI with **3 subcommands**:
- `generate` - Main workflow (generate cleaning functions)
- `analyze` - Dry-run mode (analyze without generating)
- `resume` - Resume from checkpoint

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CLI framework | argparse | stdlib, no dependencies |
| Backend config | `--backend` flag + env var | Simple, explicit |
| Instructions | `--instructions` or `@file` | Flexibility for short/long |
| Subcommands | 3 commands | Clean separation of concerns |
| Output location | `--output` flag | Configurable, defaults to cwd |

## Proposed CLI Interface

```bash
# Generate cleaning functions (main workflow)
recursive-cleaner generate data.jsonl \
  --backend mlx:model-path \
  --instructions "Normalize phones to E.164" \
  --output cleaning_functions.py \
  --tui

# Analyze without generating (dry-run)
recursive-cleaner analyze data.jsonl \
  --backend mlx:model-path \
  --instructions @instructions.txt

# Resume from checkpoint
recursive-cleaner resume cleaning_state.json \
  --backend mlx:model-path
```

## Parameter Mapping Summary

- **23 DataCleaner params** → **~15 CLI flags** (sensible defaults for the rest)
- Most flags are optional with good defaults
- Required: `FILE`, `--backend`, `--instructions`

## Risks Identified

| Risk | Mitigation |
|------|------------|
| Backend factory complexity | Start with MLX only, extensible pattern |
| Too many flags overwhelming | Group into basic/advanced in help |
| Instructions escaping issues | Support `@file` for complex instructions |

## Open Questions for User

1. **Backend syntax**: Should we use `mlx:model-path` or `--backend-type mlx --model path`?
2. **Default backend**: Error if not specified, or try to auto-detect?
3. **v0.9.0 scope**: Include `apply` command or defer to v1.0.0?

## Estimated Lines

| Component | Lines |
|-----------|-------|
| `cli.py` | ~180 |
| `__main__.py` | ~5 |
| Tests | ~150 |
| **Total** | ~335 |

---

**Awaiting user approval to proceed to contracts.**
