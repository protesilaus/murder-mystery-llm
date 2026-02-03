"""Game routes."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Request, HTTPException
from pydantic import BaseModel, Field

from mmllm.agents.base import Agent
from mmllm.agents.llm_agent import LLMAgent
from mmllm.agents.summary_agent import SummaryAgent
from mmllm.agents.scripted_agent import ScriptedAgent
from mmllm.data.event_log import append_events, write_events
from mmllm.data.party_config import load_party_config
from mmllm.core.types import EventType, GameEvent, Visibility
from mmllm.game.engine import GameEngine
from mmllm.game.loop import GameLoop
from mmllm.llm.local_client import LocalClient
from mmllm.llm.prompt_builder import load_game_config, load_prompt_templates

router = APIRouter()

_GAMES: Dict[str, GameEngine] = {}
_AGENTS: Dict[str, Dict[str, Agent]] = {}
_SUMMARY_AGENTS: Dict[str, SummaryAgent | None] = {}
_DISPLAY_NAMES: Dict[str, Dict[str, str]] = {}
logger = logging.getLogger("mmllm.web.games")


class CreateGameRequest(BaseModel):
    game_id: Optional[str] = None
    player_ids: Optional[List[str]] = None
    murderer_id: Optional[str] = None
    agent_type: str = Field("scripted", description="scripted or ollama")
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1:8b"


class RunGameRequest(BaseModel):
    max_rounds: int = Field(10, ge=1, le=50)


class InterjectRequest(BaseModel):
    body: str
    visibility: str = Field("public", description="public or private")
    to_player_id: str | None = None
    speaker_id: str = "narrator"
    record_history: bool = True


class RewindRequest(BaseModel):
    event_index: int = Field(..., ge=-1)


@router.get("/")
def list_games():
    return {"games": list(_GAMES.keys())}


@router.get("/{game_id}")
def get_game(game_id: str):
    engine = _GAMES.get(game_id)
    if engine is None:
        return {"error": "not_found"}
    return {
        "game_id": game_id,
        "murderer_id": engine.runtime.murderer_id,
        "detective_id": engine.runtime.detective_id,
        "display_names": _DISPLAY_NAMES.get(game_id, {}),
        "public_state": engine.runtime.public_state.model_dump(),
        "public_memory": engine.runtime.public_memory.model_dump(),
        "events": [evt.model_dump() for evt in engine.runtime.event_history],
    }


def _log_path(request: Request, game_id: str) -> Path:
    run_dir = getattr(request.app.state, "run_dir", Path.cwd() / "runs")
    return Path(run_dir) / game_id / "events.jsonl"


def _append_game_events(request: Request, game_id: str, events) -> None:
    if not events:
        return
    append_events(_log_path(request, game_id), events)


@router.post("/")
def create_game(
    request: Request,
    payload: CreateGameRequest = Body(default_factory=CreateGameRequest),
):
    try:
        data = payload
        config = load_game_config()
        party = load_party_config(player_count=config.player_count)
        party_players = party.get("party", {}).get("players", [])
        display_lookup = {}
        for player in party_players:
            if not isinstance(player, dict):
                continue
            pid = str(player.get("player_id", "")).strip().lower()
            if not pid:
                continue
            display_name = str(player.get("display_name", "")).strip()
            if not display_name:
                display_name = str(player.get("character_name", "")).strip()
            display_lookup[pid] = display_name

        player_ids = data.player_ids
        if not player_ids:
            player_ids = [
                str(p.get("player_id", "")).strip().lower()
                for p in party_players
                if str(p.get("player_id", "")).strip()
            ]
        if not player_ids:
            player_ids = [f"p{i+1}" for i in range(config.player_count)]
        game_id = data.game_id or f"game_{len(_GAMES) + 1:03d}"
        engine = GameEngine(
            game_id=game_id,
            player_ids=player_ids,
            murderer_id=data.murderer_id,
            actions_per_player=config.actions_per_player,
        )
        start_events = engine.start()
        _GAMES[engine.runtime.public_state.game_id] = engine
        _DISPLAY_NAMES[engine.runtime.public_state.game_id] = {
            pid: display_lookup.get(pid, pid) or pid for pid in player_ids
        }
        if data.agent_type == "ollama":
            templates = load_prompt_templates()
            client = LocalClient(
                data.ollama_base_url,
                data.ollama_model,
                system_prompt=templates.system_town,
                user_prompt=templates.user,
            )
            agents: Dict[str, Agent] = {
                pid: LLMAgent(client, system_prompt="")
                for pid in player_ids
            }
            summary_client = LocalClient(
                data.ollama_base_url,
                data.ollama_model,
            )
            _SUMMARY_AGENTS[engine.runtime.public_state.game_id] = SummaryAgent(
                summary_client,
                templates.summary_system,
                templates.summary_user,
            )
        else:
            agents = {pid: ScriptedAgent(seed=idx) for idx, pid in enumerate(player_ids)}
            _SUMMARY_AGENTS[engine.runtime.public_state.game_id] = None
        _AGENTS[engine.runtime.public_state.game_id] = agents
        _append_game_events(request, engine.runtime.public_state.game_id, start_events)
        return {
            "game_id": engine.runtime.public_state.game_id,
            "phase": engine.runtime.public_state.phase,
            "round_num": engine.runtime.public_state.round_num,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{game_id}/advance")
def advance_phase(game_id: str, request: Request):
    engine = _GAMES.get(game_id)
    if engine is None:
        return {"error": "not_found"}
    events = engine.advance_phase()
    _append_game_events(request, game_id, events)
    return {
        "phase": engine.runtime.public_state.phase,
        "murderer_id": engine.runtime.murderer_id,
        "detective_id": engine.runtime.detective_id,
        "display_names": _DISPLAY_NAMES.get(game_id, {}),
        "events": [e.model_dump() for e in events],
    }


@router.post("/{game_id}/resolve_votes")
def resolve_votes(game_id: str, request: Request):
    engine = _GAMES.get(game_id)
    if engine is None:
        return {"error": "not_found"}
    events = engine.resolve_votes()
    _append_game_events(request, game_id, events)
    return {
        "murderer_id": engine.runtime.murderer_id,
        "detective_id": engine.runtime.detective_id,
        "display_names": _DISPLAY_NAMES.get(game_id, {}),
        "events": [e.model_dump() for e in events],
    }


@router.post("/{game_id}/auto")
def run_game(
    game_id: str,
    request: Request,
    payload: RunGameRequest = Body(default_factory=RunGameRequest),
):
    engine = _GAMES.get(game_id)
    if engine is None:
        return {"error": "not_found"}
    agents = _AGENTS.get(game_id)
    if agents is None:
        agents = {p.player_id: ScriptedAgent(seed=idx) for idx, p in enumerate(engine.runtime.public_state.players)}
        _AGENTS[game_id] = agents
    summary_agent = _SUMMARY_AGENTS.get(game_id)

    data = payload
    loop = GameLoop(engine, agents, summary_agent=summary_agent)
    before = len(engine.runtime.event_history)
    loop.run_until_end(max_rounds=data.max_rounds)
    _append_game_events(request, game_id, engine.runtime.event_history[before:])
    return {
        "phase": engine.runtime.public_state.phase,
        "round_num": engine.runtime.public_state.round_num,
        "murderer_id": engine.runtime.murderer_id,
        "detective_id": engine.runtime.detective_id,
        "display_names": _DISPLAY_NAMES.get(game_id, {}),
        "public_state": engine.runtime.public_state.model_dump(),
        "events": [evt.model_dump() for evt in engine.runtime.event_history],
    }


@router.post("/{game_id}/round")
def run_round(game_id: str, request: Request):
    engine = _GAMES.get(game_id)
    if engine is None:
        logger.warning("run_round missing game_id=%s", game_id)
        return {"error": "not_found"}
    agents = _AGENTS.get(game_id)
    if agents is None:
        agents = {p.player_id: ScriptedAgent(seed=idx) for idx, p in enumerate(engine.runtime.public_state.players)}
        _AGENTS[game_id] = agents
    summary_agent = _SUMMARY_AGENTS.get(game_id)

    try:
        public_state = engine.runtime.public_state
        alive_ids = [p.player_id for p in public_state.players if p.alive]
        agent_types = {pid: type(agent).__name__ for pid, agent in agents.items()}
        logger.info(
            "run_round start game_id=%s phase=%s round=%s alive=%s agents=%s",
            game_id,
            public_state.phase,
            public_state.round_num,
            alive_ids,
            agent_types,
        )
        loop = GameLoop(engine, agents, summary_agent=summary_agent)
        before = len(engine.runtime.event_history)
        loop.run_round()
        new_events = engine.runtime.event_history[before:]
        _append_game_events(request, game_id, new_events)
        logger.info(
            "run_round done game_id=%s phase=%s round=%s new_events=%s total_events=%s",
            game_id,
            engine.runtime.public_state.phase,
            engine.runtime.public_state.round_num,
            len(new_events),
            len(engine.runtime.event_history),
        )
        return {
            "phase": engine.runtime.public_state.phase,
            "round_num": engine.runtime.public_state.round_num,
            "murderer_id": engine.runtime.murderer_id,
            "detective_id": engine.runtime.detective_id,
            "display_names": _DISPLAY_NAMES.get(game_id, {}),
            "public_state": engine.runtime.public_state.model_dump(),
            "events": [evt.model_dump() for evt in engine.runtime.event_history],
        }
    except Exception as exc:  # noqa: BLE001
        phase = getattr(engine.runtime.public_state, "phase", None)
        round_num = getattr(engine.runtime.public_state, "round_num", None)
        logger.exception(
            "run_round failed game_id=%s phase=%s round=%s",
            game_id,
            phase,
            round_num,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{game_id}/action")
def run_action(game_id: str, request: Request):
    engine = _GAMES.get(game_id)
    if engine is None:
        logger.warning("run_action missing game_id=%s", game_id)
        return {"error": "not_found"}
    agents = _AGENTS.get(game_id)
    if agents is None:
        agents = {p.player_id: ScriptedAgent(seed=idx) for idx, p in enumerate(engine.runtime.public_state.players)}
        _AGENTS[game_id] = agents
    summary_agent = _SUMMARY_AGENTS.get(game_id)

    try:
        public_state = engine.runtime.public_state
        logger.info(
            "run_action start game_id=%s phase=%s round=%s",
            game_id,
            public_state.phase,
            public_state.round_num,
        )
        loop = GameLoop(engine, agents, summary_agent=summary_agent)
        before = len(engine.runtime.event_history)
        loop.step_action()
        new_events = engine.runtime.event_history[before:]
        _append_game_events(request, game_id, new_events)
        logger.info(
            "run_action done game_id=%s phase=%s round=%s new_events=%s total_events=%s",
            game_id,
            engine.runtime.public_state.phase,
            engine.runtime.public_state.round_num,
            len(new_events),
            len(engine.runtime.event_history),
        )
        return {
            "phase": engine.runtime.public_state.phase,
            "round_num": engine.runtime.public_state.round_num,
            "murderer_id": engine.runtime.murderer_id,
            "detective_id": engine.runtime.detective_id,
            "display_names": _DISPLAY_NAMES.get(game_id, {}),
            "public_state": engine.runtime.public_state.model_dump(),
            "events": [evt.model_dump() for evt in engine.runtime.event_history],
        }
    except Exception as exc:  # noqa: BLE001
        phase = getattr(engine.runtime.public_state, "phase", None)
        round_num = getattr(engine.runtime.public_state, "round_num", None)
        logger.exception(
            "run_action failed game_id=%s phase=%s round=%s",
            game_id,
            phase,
            round_num,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{game_id}/interject")
def interject(game_id: str, request: Request, payload: InterjectRequest):
    engine = _GAMES.get(game_id)
    if engine is None:
        return {"error": "not_found"}

    speaker_id = payload.speaker_id.strip().lower()
    visibility = payload.visibility.strip().lower()
    body = payload.body.strip()
    if not body:
        return {"error": "empty_body"}
    if visibility == "private" and not payload.to_player_id:
        return {"error": "missing_target"}

    event = GameEvent(
        event_id=f"evt_{uuid4().hex[:8]}",
        game_id=engine.runtime.public_state.game_id,
        ts_utc=datetime.now(timezone.utc).isoformat(),
        event_type=EventType.message_public if visibility == "public" else EventType.message_private,
        round_num=engine.runtime.public_state.round_num,
        phase=engine.runtime.public_state.phase,
        actor_id=speaker_id,
        visibility=Visibility(mode="public" if visibility == "public" else "direct", to=[]),
        payload={"body": body},
    )

    if visibility == "private":
        to_player = (payload.to_player_id or "").strip().lower()
        event.payload["to"] = to_player
        event.visibility = Visibility(mode="direct", to=[speaker_id, to_player])

    if payload.record_history:
        engine.runtime.event_history.append(event)
        engine._apply_event(event)
        _append_game_events(request, game_id, [event])

    return {"ok": True, "recorded": payload.record_history, "event": event.model_dump()}


@router.post("/{game_id}/rewind")
def rewind_game(game_id: str, request: Request, payload: RewindRequest):
    engine = _GAMES.get(game_id)
    if engine is None:
        return {"error": "not_found"}

    events = engine.runtime.event_history
    idx = payload.event_index
    if idx < -1:
        idx = -1
    if idx >= len(events):
        idx = len(events) - 1

    new_events = [] if idx == -1 else events[: idx + 1]
    engine.rebuild_from_events(new_events)
    write_events(_log_path(request, game_id), new_events)

    return {
        "phase": engine.runtime.public_state.phase,
        "round_num": engine.runtime.public_state.round_num,
        "murderer_id": engine.runtime.murderer_id,
        "detective_id": engine.runtime.detective_id,
        "display_names": _DISPLAY_NAMES.get(game_id, {}),
        "public_state": engine.runtime.public_state.model_dump(),
        "events": [evt.model_dump() for evt in engine.runtime.event_history],
    }
