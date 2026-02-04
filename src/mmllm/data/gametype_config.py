"""Game type configuration loading and management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from mmllm.core.game_config import GameTypeConfig


_GAMETYPE_CACHE: Dict[str, GameTypeConfig] = {}


def _gametypes_dir() -> Path:
    """Return the gametypes configuration directory."""
    return Path.cwd() / "configs" / "gametypes"


def list_game_types() -> List[str]:
    """Return list of available game type names."""
    gametypes_dir = _gametypes_dir()
    names = ["classic"]  # Always available as built-in default

    if gametypes_dir.exists():
        for path in gametypes_dir.glob("*.json"):
            name = path.stem
            if name not in names:
                names.append(name)

    return sorted(names)


def load_game_type(name: str = "classic", *, use_cache: bool = True) -> GameTypeConfig:
    """Load a game type configuration by name.

    Args:
        name: Name of the game type (without .json extension)
        use_cache: Whether to use cached configs

    Returns:
        GameTypeConfig instance

    Raises:
        FileNotFoundError: If game type file doesn't exist
        ValidationError: If config file is invalid
    """
    if use_cache and name in _GAMETYPE_CACHE:
        return _GAMETYPE_CACHE[name]

    # Classic is always available as built-in
    if name == "classic":
        config = GameTypeConfig.default_classic()
        if use_cache:
            _GAMETYPE_CACHE[name] = config
        return config

    # Try to load from file
    path = _gametypes_dir() / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Game type '{name}' not found at {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    config = GameTypeConfig.model_validate(data)

    if use_cache:
        _GAMETYPE_CACHE[name] = config

    return config


def save_game_type(config: GameTypeConfig, *, name: Optional[str] = None) -> Path:
    """Save a game type configuration to file.

    Args:
        config: The configuration to save
        name: Override name (defaults to config.name)

    Returns:
        Path to the saved file
    """
    name = name or config.name
    gametypes_dir = _gametypes_dir()
    gametypes_dir.mkdir(parents=True, exist_ok=True)

    path = gametypes_dir / f"{name}.json"
    path.write_text(
        config.model_dump_json(indent=2),
        encoding="utf-8",
    )

    # Invalidate cache
    if name in _GAMETYPE_CACHE:
        del _GAMETYPE_CACHE[name]

    return path


def clear_cache() -> None:
    """Clear the game type configuration cache."""
    _GAMETYPE_CACHE.clear()
