"""Party configuration persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import yaml

from mmllm.llm.prompt_builder import load_game_config


def _party_path(config_path: Path | None = None) -> Path:
    if config_path is not None:
        return config_path
    return Path.cwd() / "configs" / "party.json"


def _party_defaults_path() -> Path:
    return Path.cwd() / "configs" / "party_defaults.yaml"


def _load_party_defaults() -> Dict[str, object]:
    path = _party_defaults_path()
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    party = data.get("party", {})
    return party if isinstance(party, dict) else {}


def load_party_defaults() -> Dict[str, object]:
    """Return party defaults/ranges from YAML."""
    return _load_party_defaults()


def _default_players(
    count: int, defaults: Dict[str, object]
) -> List[Dict[str, object]]:
    display_name_template = str(defaults.get("display_name", "Agent {index}"))
    character_name_template = str(defaults.get("character_name", ""))
    score_default = defaults.get("score", 0)
    return [
        {
            "player_id": f"p{i + 1}",
            "display_name": _apply_template(display_name_template, i + 1),
            "character_name": _apply_template(character_name_template, i + 1),
            "score": score_default,
        }
        for i in range(count)
    ]


def _apply_template(template: str, index: int) -> str:
    try:
        return template.format(index=index)
    except (KeyError, ValueError):
        return template


def load_party_config(
    config_path: Path | None = None,
    *,
    player_count: int | None = None,
    create_if_missing: bool = True,
) -> Dict[str, object]:
    path = _party_path(config_path)
    if player_count is None:
        player_count = load_game_config().player_count
    party_defaults = _load_party_defaults()
    defaults = (
        party_defaults.get("defaults", {})
        if isinstance(party_defaults.get("defaults", {}), dict)
        else {}
    )

    if not path.exists():
        legacy_path = Path.cwd() / "configs" / "party.yaml"
        data: Dict[str, object] = {}
        if legacy_path.exists():
            legacy = yaml.safe_load(legacy_path.read_text(encoding="utf-8")) or {}
            if isinstance(legacy, dict):
                data = legacy
        if not data:
            data = {"party": {"players": _default_players(player_count, defaults)}}
        if create_if_missing:
            save_party_config(data, config_path=path)
        return data

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    party = data.get("party", {}) if isinstance(data.get("party", {}), dict) else {}
    players = party.get("players", [])
    if not isinstance(players, list):
        players = []

    normalized: List[Dict[str, object]] = []
    seen = set()
    for entry in players:
        if not isinstance(entry, dict):
            continue
        pid = str(entry.get("player_id", "")).strip().lower()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        normalized.append(
            {
                "player_id": pid,
                "display_name": str(entry.get("display_name", pid)).strip()
                or _apply_template(
                    str(defaults.get("display_name", pid)), len(normalized) + 1
                ),
                "character_name": str(entry.get("character_name", "")).strip()
                or _apply_template(
                    str(defaults.get("character_name", "")), len(normalized) + 1
                ),
                "score": entry.get("score", 0),
            }
        )

    if len(normalized) < player_count:
        for idx in range(len(normalized), player_count):
            pid = f"p{idx + 1}"
            if pid in seen:
                continue
            normalized.append(
                {
                    "player_id": pid,
                    "display_name": _apply_template(
                        str(defaults.get("display_name", f"Agent {idx + 1}")), idx + 1
                    ),
                    "character_name": _apply_template(
                        str(defaults.get("character_name", "")), idx + 1
                    ),
                    "score": defaults.get("score", 0),
                }
            )
    elif len(normalized) > player_count:
        normalized = normalized[:player_count]

    data["party"] = {"players": normalized}
    if create_if_missing:
        save_party_config(data, config_path=path)
    return data


def save_party_config(
    data: Dict[str, object], *, config_path: Path | None = None
) -> None:
    path = _party_path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
