"""Filesystem paths and run folders."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def new_run_dir(base: Path) -> Path:
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    run_dir = base / f"run_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
