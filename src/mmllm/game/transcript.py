"""Public transcript handling with redaction rules."""

from dataclasses import dataclass, field
from typing import List

from mmllm.core.types import GameEvent


@dataclass
class Transcript:
    events: List[GameEvent] = field(default_factory=list)

    def add(self, event: GameEvent) -> None:
        self.events.append(event)

    def public_view(self) -> List[GameEvent]:
        return list(self.events)
