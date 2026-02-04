"""Shared utility functions for the game engine."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4


def ts_utc() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def event_id(prefix: str = "evt") -> str:
    """Generate a unique event ID with the given prefix."""
    return f"{prefix}_{uuid4().hex[:8]}"


# Regex pattern for extracting JSON from code fences
CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def normalize_player_id(player_id: str) -> str:
    """Normalize a player ID to lowercase with whitespace stripped."""
    return player_id.strip().lower()
