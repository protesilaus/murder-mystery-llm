"""Seeded randomness utilities."""

from __future__ import annotations

import random
from typing import Iterable, List, Sequence, TypeVar

T = TypeVar("T")


class RNG:
    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)

    def choice(self, items: Sequence[T]) -> T:
        return self._random.choice(items)

    def shuffle(self, items: List[T]) -> None:
        self._random.shuffle(items)

    def sample(self, items: Sequence[T], k: int) -> List[T]:
        return self._random.sample(items, k)

    def randint(self, a: int, b: int) -> int:
        return self._random.randint(a, b)

    def seed(self, seed: int | None) -> None:
        self._random.seed(seed)


def seeded_shuffle(items: Iterable[T], seed: int | None) -> List[T]:
    rng = RNG(seed)
    result = list(items)
    rng.shuffle(result)
    return result
