"""JSON schemas for strict outputs."""

ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "target": {"type": "string"},
    },
    "required": ["type"],
}
