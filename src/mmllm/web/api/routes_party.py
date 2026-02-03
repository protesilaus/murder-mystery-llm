"""Party configuration routes."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from mmllm.data.party_config import load_party_config, load_party_defaults, save_party_config
from mmllm.llm.prompt_builder import build_party_name_messages, load_game_config, load_prompt_templates

router = APIRouter()

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class PartyPlayer(BaseModel):
    player_id: str
    display_name: str = ""
    character_name: str = ""
    score: float | int = 0


class PartyUpdateRequest(BaseModel):
    players: List[PartyPlayer]


class PartyGenerateRequest(BaseModel):
    base_url: str = Field("http://127.0.0.1:11434")
    model: str = Field("llama3.1:8b")


@router.get("/")
def get_party():
    config = load_game_config()
    data = load_party_config(player_count=config.player_count)
    defaults = load_party_defaults()
    return {
        "players": data.get("party", {}).get("players", []),
        "player_count": config.player_count,
        "defaults": defaults.get("defaults", {}),
        "ranges": defaults.get("ranges", {}),
    }


@router.post("/")
def save_party(payload: PartyUpdateRequest = Body(...)):
    players = [p.model_dump() for p in payload.players]
    data = {"party": {"players": players}}
    save_party_config(data)
    return {"ok": True, "players": players}


@router.post("/generate")
def generate_party_names(payload: PartyGenerateRequest = Body(...)):
    config = load_game_config()
    data = load_party_config(player_count=config.player_count)
    players = data.get("party", {}).get("players", [])
    player_ids = [str(p.get("player_id", "")).strip().lower() for p in players]
    player_ids = [pid for pid in player_ids if pid]
    templates = load_prompt_templates()
    messages = build_party_name_messages(
        player_ids,
        templates.party_name_system,
        templates.party_name_user,
    )

    body = {"model": payload.model, "stream": False, "messages": messages}
    response = _post_json(f"{payload.base_url.rstrip('/')}/api/chat", body)
    content = response.get("message", {}).get("content", "")
    names = _parse_names(content, len(player_ids))

    updated = []
    for idx, player in enumerate(players):
        name = names[idx] if idx < len(names) else player.get("display_name", "")
        updated.append(
            {
                "player_id": player.get("player_id", f"p{idx+1}"),
                "display_name": name or f"Agent {idx+1}",
                "character_name": player.get("character_name", ""),
                "score": player.get("score", 0),
            }
        )

    save_party_config({"party": {"players": updated}})
    return {"ok": True, "players": updated}


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc


def _parse_names(content: str, count: int) -> List[str]:
    text = content.strip()
    match = _CODE_FENCE_RE.search(text)
    if match:
        text = match.group(1).strip()

    names: List[str] = []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            names = [str(x).strip() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        names = []

    if len(names) < count:
        for idx in range(len(names), count):
            names.append(f"Agent {idx+1}")
    return names[:count]
