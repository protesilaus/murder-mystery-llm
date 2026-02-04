"""JSON schemas for strict outputs."""

# Schema for the complete response including the action object
COMPLETE_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "request_id": {"type": "string"},
        "game_id": {"type": "string"},
        "player_id": {"type": "string"},
        "round_num": {"type": "integer"},
        "phase": {"type": "string"},
        "action": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "reasoning_private": {"type": "string"},
                "body": {"type": "string"},
                "target_player_id": {"type": "string"},
                "to_player_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["type"],
        },
        "suspicion_scores": {"type": "object"},
    },
    "required": ["action"],
}

# Schema for just the action object (legacy)
ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "target": {"type": "string"},
    },
    "required": ["type"],
}
