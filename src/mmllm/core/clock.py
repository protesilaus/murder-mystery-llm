"""Round/phase progression helpers."""

from dataclasses import dataclass
from typing import List

from mmllm.core.types import Phase


@dataclass
class PhaseClock:
    phases: List[Phase]
    index: int = 0
    round: int = 1

    def current(self) -> Phase:
        return self.phases[self.index]

    def advance(self) -> Phase:
        self.index = (self.index + 1) % len(self.phases)
        if self.index == 0:
            self.round += 1
        return self.current()
