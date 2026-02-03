"""Tournament evaluation metrics."""

from typing import Dict


def evaluate(results: list[dict]) -> Dict[str, float]:
    return {"games": float(len(results))}
