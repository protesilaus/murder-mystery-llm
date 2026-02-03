"""Build supervised datasets from logs."""

from pathlib import Path
from typing import List


def build_dataset(log_paths: List[Path]) -> list[dict]:
    return [{"path": str(path)} for path in log_paths]
