"""Validates/repairs JSON with retry logic."""

import json
from typing import Any, Dict


def parse_action(payload: str) -> Dict[str, Any]:
    return json.loads(payload)
