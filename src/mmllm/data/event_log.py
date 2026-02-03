"""JSONL writer/reader for events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator

from mmllm.core.types import GameEvent


def write_events(path: Path, events: Iterable[GameEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event.model_dump()) + "\n")


def append_events(path: Path, events: Iterable[GameEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event.model_dump()) + "\n")


def read_events(path: Path) -> Iterator[GameEvent]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            yield GameEvent(**payload)
