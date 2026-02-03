"""ID helpers that enforce lower-case identifiers."""

import re

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_\-]*$")


def normalize_id(value: str) -> str:
    """Normalize a string into a valid lower-case id."""
    return re.sub(r"\s+", "-", value.strip().lower())


def is_valid_id(value: str) -> bool:
    """Return True if the value matches the id pattern."""
    return bool(_ID_PATTERN.fullmatch(value))
