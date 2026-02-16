#!/bin/bash
# Comprehensive benchmark across Qwen3 MLX model sizes.
# Each model runs in a separate process (MLX models can't share memory).
#
# Usage:
#   ./benchmarks/run_all.sh           # Run all models
#   ./benchmarks/run_all.sh --warmup  # With warmup generation
#
# Models are sorted by active parameter count (smallest to largest).
# All lmstudio-community. 8-bit except 80B models (4-bit to fit in memory).
# 2507 = newer instruct revision (only available for 4B and 30B-A3B).
#
# All model IDs verified on HuggingFace 2026-02-11.
#
# After each model completes, its HF cache is deleted to save disk space.

set -e

EXTRA_ARGS="${@}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNNER="python ${SCRIPT_DIR}/run_benchmark.py"
HF_CACHE="${HF_HOME:-${HOME}/.cache/huggingface}/hub"

MODELS=(
    # Dense models, 8-bit
    "lmstudio-community/Qwen3-4B-Instruct-2507-MLX-8bit"              # 4B active, 2507
    "lmstudio-community/Qwen3-8B-MLX-8bit"                            # 8B active, original
    "lmstudio-community/Qwen3-14B-MLX-8bit"                           # 14B active, original

    # MoE models, 8-bit
    "lmstudio-community/Qwen3-30B-A3B-Instruct-2507-MLX-8bit"         # 3B active / 30B total, 2507
    "lmstudio-community/Qwen3-Coder-30B-A3B-Instruct-MLX-8bit"        # 3B active / 30B total, coder

    # Large MoE models, 4-bit (too big for 8-bit)
    "lmstudio-community/Qwen3-Coder-Next-MLX-4bit"                    # 3B active / 80B total, coder
    "lmstudio-community/Qwen3-Next-80B-A3B-Instruct-MLX-4bit"         # 3.9B active / 80B total
)

cleanup_model() {
    # Convert org/model-name to HF cache directory format: models--org--model-name
    local model_id="$1"
    local cache_dir="${HF_CACHE}/models--$(echo "${model_id}" | sed 's|/|--|g')"
    if [ -d "${cache_dir}" ]; then
        local size=$(du -sh "${cache_dir}" 2>/dev/null | cut -f1)
        rm -rf "${cache_dir}"
        echo "  Cleaned up ${size} from HF cache: $(basename ${cache_dir})"
    fi
}

echo "============================================="
echo "  Recursive Data Cleaner — Full Benchmark"
echo "============================================="
echo ""
echo "Models to benchmark: ${#MODELS[@]}"
echo "Extra args: ${EXTRA_ARGS:-none}"
echo "HF cache: ${HF_CACHE}"
echo ""

echo "============================================="
echo "  Recursive Data Cleaner — Full Benchmark"
echo "============================================="
echo ""
echo "Models to benchmark: ${#MODELS[@]}"
echo "Extra args: ${EXTRA_ARGS:-none}"
echo ""

RESULTS_DIR="${SCRIPT_DIR}/results"
mkdir -p "${RESULTS_DIR}"

for MODEL in "${MODELS[@]}"; do
    SHORT_NAME=$(echo "$MODEL" | sed 's|.*/||')
    echo ""
    echo "============================================="
    echo "  Model: ${SHORT_NAME}"
    echo "============================================="
    echo ""

    ${RUNNER} --model "${MODEL}" --output-dir "${RESULTS_DIR}" ${EXTRA_ARGS} || {
        echo "  FAILED: ${SHORT_NAME} (skipping)"
        echo "${SHORT_NAME}: FAILED" >> "${RESULTS_DIR}/failures.log"
        cleanup_model "${MODEL}"
        continue
    }

    echo ""
    echo "  Done: ${SHORT_NAME}"

    # Free disk space — delete model files from HF cache
    cleanup_model "${MODEL}"
done

echo ""
echo "============================================="
echo "  All benchmarks complete!"
echo "  Results in: ${RESULTS_DIR}/"
echo "============================================="
