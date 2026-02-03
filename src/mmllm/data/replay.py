"""Replay games from logs."""

from pathlib import Path

from mmllm.data.event_log import read_events


def replay_events(path: Path):
    return list(read_events(path))
