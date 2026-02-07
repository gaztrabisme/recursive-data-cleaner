"""State persistence for the cleaning pipeline."""

import json
import os
from datetime import datetime, timezone

STATE_VERSION = "0.5.0"


def save_state(
    state_file: str,
    file_path: str,
    instructions: str,
    chunk_size: int,
    last_completed_chunk: int,
    total_chunks: int,
    functions: list[dict],
    optimize: bool,
    optimize_threshold: int,
    early_termination: bool,
    saturation_check_interval: int,
) -> None:
    """Save pipeline state to JSON file with atomic write."""
    state = {
        "version": STATE_VERSION,
        "file_path": file_path,
        "instructions": instructions,
        "chunk_size": chunk_size,
        "last_completed_chunk": last_completed_chunk,
        "total_chunks": total_chunks,
        "functions": functions,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "optimize": optimize,
        "optimize_threshold": optimize_threshold,
        "early_termination": early_termination,
        "saturation_check_interval": saturation_check_interval,
    }
    tmp_path = state_file + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2)
    os.rename(tmp_path, state_file)


def load_state(state_file: str, expected_file_path: str) -> dict:
    """
    Load state from JSON file.

    Args:
        state_file: Path to the state JSON file
        expected_file_path: The file_path the caller expects (for validation)

    Returns:
        Dict with keys: functions, last_completed_chunk, total_chunks

    Raises:
        ValueError: If state file is invalid or file_path mismatches
    """
    try:
        with open(state_file) as f:
            state = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid state file JSON: {e}")

    if state.get("file_path") != expected_file_path:
        raise ValueError(
            f"State file_path mismatch: state has '{state.get('file_path')}', "
            f"but current file_path is '{expected_file_path}'"
        )

    return {
        "functions": state.get("functions", []),
        "last_completed_chunk": state.get("last_completed_chunk", -1),
        "total_chunks": state.get("total_chunks", 0),
    }


def load_state_for_resume(state_file: str) -> dict:
    """
    Load full state for the resume() classmethod.

    Args:
        state_file: Path to state JSON file

    Returns:
        Full state dict

    Raises:
        FileNotFoundError: If state file doesn't exist
        ValueError: If state file is invalid JSON
    """
    if not os.path.exists(state_file):
        raise FileNotFoundError(f"State file not found: {state_file}")
    try:
        with open(state_file) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid state file JSON: {e}")
