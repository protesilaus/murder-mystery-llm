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
from mmllm.core.types import (
    ActionResponse,
    ActionType,
    EventType,
    GameEvent,
    InvestigateAction,
    KillAction,
    PassAction,
    PollAction,
    QuestionAction,
    SpeakAction,
    Visibility,
    VoteAction,
)
from mmllm.game.engine import GameEngine
from mmllm.game.loop import GameLoop
from mmllm.game.rules import legal_actions
from mmllm.llm.local_client import LocalClient
from mmllm.llm.prompt_builder import load_game_config, load_prompt_templates

router = APIRouter()

_GAMES: Dict[str, GameEngine] = {}
_AGENTS: Dict[str, Dict[str, Agent]] = {}
_SUMMARY_AGENTS: Dict[str, SummaryAgent | None] = {}
_DISPLAY_NAMES: Dict[str, Dict[str, str]] = {}
_PROMPT_STORE: Dict[str, Dict[str, dict]] = {}  # {game_id: {request_id: prompt_data}}
logger = logging.getLogger("mmllm.web.games")


def _store_prompt(game_id: str, request_id: str, data: dict) -> None:
    """Store LLM prompt for later retrieval."""
    if game_id not in _PROMPT_STORE:
        _PROMPT_STORE[game_id] = {}
    _PROMPT_STORE[game_id][request_id] = data


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


class UpdateAPRequest(BaseModel):
    ap: int = Field(..., ge=0, le=20)


class AIChatRequest(BaseModel):
    message: str


class AIGenerateActionRequest(BaseModel):
    action_type: str


class ForceActionRequest(BaseModel):
    action_type: str
    player_id: Optional[str] = None  # If not provided, use current turn player
    details: Optional[Dict] = None


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
            player_ids = [f"p{i + 1}" for i in range(config.player_count)]
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
                prompt_callback=_store_prompt,
            )
            agents: Dict[str, Agent] = {
                pid: LLMAgent(client, system_prompt="") for pid in player_ids
            }
            summary_client = LocalClient(
                data.ollama_base_url,
                data.ollama_model,
                prompt_callback=_store_prompt,
            )
            _SUMMARY_AGENTS[engine.runtime.public_state.game_id] = SummaryAgent(
                summary_client,
                templates.summary_system,
                templates.summary_user,
            )
        else:
            agents = {
                pid: ScriptedAgent(seed=idx) for idx, pid in enumerate(player_ids)
            }
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
        agents = {
            p.player_id: ScriptedAgent(seed=idx)
            for idx, p in enumerate(engine.runtime.public_state.players)
        }
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
        agents = {
            p.player_id: ScriptedAgent(seed=idx)
            for idx, p in enumerate(engine.runtime.public_state.players)
        }
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
        agents = {
            p.player_id: ScriptedAgent(seed=idx)
            for idx, p in enumerate(engine.runtime.public_state.players)
        }
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
        event_type=EventType.message_public
        if visibility == "public"
        else EventType.message_private,
        round_num=engine.runtime.public_state.round_num,
        phase=engine.runtime.public_state.phase,
        actor_id=speaker_id,
        visibility=Visibility(
            mode="public" if visibility == "public" else "direct", to=[]
        ),
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


@router.patch("/{game_id}/players/{player_id}/ap")
def update_player_ap(game_id: str, player_id: str, payload: UpdateAPRequest):
    engine = _GAMES.get(game_id)
    if engine is None:
        return {"error": "not_found"}

    player_id_lower = player_id.strip().lower()
    player = None
    for p in engine.runtime.public_state.players:
        if p.player_id == player_id_lower:
            player = p
            break

    if player is None:
        return {"error": "player_not_found"}

    player.social_ap = payload.ap
    return {"ok": True, "player_id": player.player_id, "social_ap": player.social_ap}


@router.post("/{game_id}/ai-chat")
async def ai_chat(game_id: str, payload: AIChatRequest):
    """Chat with the game AI about the current state."""
    engine = _GAMES.get(game_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Game not found")

    agents = _AGENTS.get(game_id)
    if not agents:
        raise HTTPException(
            status_code=400, detail="No agents configured for this game"
        )

    # Get the first LLM agent to use for chat
    llm_agent = None
    for agent in agents.values():
        if isinstance(agent, LLMAgent):
            llm_agent = agent
            break

    if llm_agent is None:
        raise HTTPException(
            status_code=400,
            detail="No LLM agents available. Game must use 'ollama' agent type.",
        )

    try:
        # Build a context message about the current game state
        public_state = engine.runtime.public_state
        alive_players = [p.player_id for p in public_state.players if p.alive]
        context = f"""Current game state:
- Phase: {public_state.phase}
- Round: {public_state.round_num}
- Alive players: {", ".join(alive_players)}
- Total events: {len(engine.runtime.event_history)}

User question: {payload.message}

Please provide a helpful response about the game state or answer the user's question."""

        # Use the LLM client directly to generate a response
        response = await llm_agent.client.generate(
            system_prompt="You are a helpful assistant that answers questions about the current game state in a murder mystery game.",
            user_prompt=context,
        )

        return {"ok": True, "response": response}
    except Exception as exc:
        logger.exception("ai_chat failed game_id=%s", game_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{game_id}/ai-generate-action")
async def ai_generate_action(game_id: str, payload: AIGenerateActionRequest):
    """Ask AI to generate action JSON for a specific action type."""
    engine = _GAMES.get(game_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Game not found")

    agents = _AGENTS.get(game_id)
    if not agents:
        raise HTTPException(
            status_code=400, detail="No agents configured for this game"
        )

    # Get the first LLM agent
    llm_agent = None
    for agent in agents.values():
        if isinstance(agent, LLMAgent):
            llm_agent = agent
            break

    if llm_agent is None:
        raise HTTPException(
            status_code=400,
            detail="No LLM agents available. Game must use 'ollama' agent type.",
        )

    try:
        public_state = engine.runtime.public_state
        current_player = None
        for p in public_state.players:
            if p.alive:
                current_player = p
                break

        if not current_player:
            raise HTTPException(status_code=400, detail="No alive players")

        alive_players = [p.player_id for p in public_state.players if p.alive]

        # Build prompt for action generation
        action_examples = {
            "speak": '{"body": "I have some thoughts to share about last night."}',
            "question": '{"target": "player_id", "body": "Where were you last night?"}',
            "poll": '{"body": "Who do you think is suspicious?"}',
            "vote": '{"target": "player_id"}',
            "pass": "{}",
        }

        prompt = f"""Generate valid JSON for a {payload.action_type} action in this murder mystery game.

Current game state:
- Phase: {public_state.phase}
- Round: {public_state.round_num}
- Current player: {current_player.player_id}
- Alive players: {", ".join(alive_players)}

Action type: {payload.action_type}
Example format: {action_examples.get(payload.action_type, "{}")}

Requirements:
- Return ONLY valid JSON, no other text
- For actions with "target", choose a random alive player (not the current player)
- For actions with "body", write something contextually appropriate
- Be creative but stay in character for a murder mystery game

Generate the JSON now:"""

        response = await llm_agent.client.generate(
            system_prompt="You are a JSON generator. Return ONLY valid JSON, no explanation or other text.",
            user_prompt=prompt,
        )

        # Try to parse the response as JSON
        import json

        try:
            # Clean up response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
            cleaned = cleaned.strip()

            action_json = json.loads(cleaned)
            return {"ok": True, "action_json": action_json, "raw_response": response}
        except json.JSONDecodeError as e:
            return {
                "ok": False,
                "error": f"Failed to parse JSON: {e}",
                "raw_response": response,
            }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ai_generate_action failed game_id=%s", game_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{game_id}/force-action")
def force_action(game_id: str, request: Request, payload: ForceActionRequest):
    """Force a specific action with provided details."""
    engine = _GAMES.get(game_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Game not found")

    try:
        # 1. Get the player ID (from payload or current turn)
        if payload.player_id:
            player_id = payload.player_id.strip().lower()
        else:
            # Use first player in turn order if available
            if engine.runtime.turn_order:
                player_id = engine.runtime.turn_order[0]
            else:
                raise HTTPException(
                    status_code=400,
                    detail="No player_id provided and no turn order available",
                )

        # 2. Validate player exists and is alive
        player = engine.runtime.get_player(player_id)
        if player is None:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
        if not player.alive:
            raise HTTPException(
                status_code=400, detail=f"Player {player_id} is not alive"
            )

        # 3. Build action from action_type and details
        details = payload.details or {}
        action_type_str = payload.action_type.strip().lower()

        # Parse action type
        try:
            action_type_enum = ActionType(action_type_str)
        except ValueError:
            allowed = ", ".join([t.value for t in ActionType])
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action_type '{action_type_str}'. Allowed: {allowed}",
            )

        # Check if action is legal
        allowed_actions = legal_actions(engine.runtime, player_id)
        if action_type_enum not in allowed_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Action '{action_type_str}' is not allowed for player {player_id} in current phase",
            )

        # Build action object
        if action_type_enum == ActionType.speak:
            if "body" not in details:
                raise HTTPException(
                    status_code=400, detail="Missing 'body' field for speak action"
                )
            action = SpeakAction(body=str(details["body"]))
        elif action_type_enum == ActionType.question:
            if "to_player_id" not in details or "body" not in details:
                raise HTTPException(
                    status_code=400,
                    detail="Missing 'to_player_id' or 'body' field for question action",
                )
            action = QuestionAction(
                to_player_id=str(details["to_player_id"]), body=str(details["body"])
            )
        elif action_type_enum == ActionType.poll:
            if "body" not in details:
                raise HTTPException(
                    status_code=400, detail="Missing 'body' field for poll action"
                )
            action = PollAction(body=str(details["body"]))
        elif action_type_enum == ActionType.vote:
            if "target_player_id" not in details:
                raise HTTPException(
                    status_code=400,
                    detail="Missing 'target_player_id' field for vote action",
                )
            action = VoteAction(target_player_id=str(details["target_player_id"]))
        elif action_type_enum == ActionType.kill:
            if "target_player_id" not in details:
                raise HTTPException(
                    status_code=400,
                    detail="Missing 'target_player_id' field for kill action",
                )
            action = KillAction(target_player_id=str(details["target_player_id"]))
        elif action_type_enum == ActionType.investigate:
            if "target_player_id" not in details:
                raise HTTPException(
                    status_code=400,
                    detail="Missing 'target_player_id' field for investigate action",
                )
            action = InvestigateAction(
                target_player_id=str(details["target_player_id"])
            )
        elif action_type_enum == ActionType.pass_turn:
            action = PassAction(note=details.get("note", ""))
        else:
            raise HTTPException(
                status_code=400, detail=f"Action type '{action_type_str}' not supported"
            )

        # 4. Create ActionResponse
        action_response = ActionResponse(
            request_id=f"force_{uuid4().hex[:8]}",
            game_id=engine.runtime.public_state.game_id,
            player_id=player_id,
            round_num=engine.runtime.public_state.round_num,
            phase=engine.runtime.public_state.phase,
            action=action,
        )

        # 5. Apply action to game engine
        before = len(engine.runtime.event_history)
        engine.apply_action(action_response)
        new_events = engine.runtime.event_history[before:]

        # 6. Record events
        _append_game_events(request, game_id, new_events)

        logger.info(
            "force_action applied game_id=%s player_id=%s action_type=%s new_events=%s",
            game_id,
            player_id,
            action_type_str,
            len(new_events),
        )

        return {
            "ok": True,
            "player_id": player_id,
            "action_type": action_type_str,
            "public_state": engine.runtime.public_state.model_dump(),
            "events": [evt.model_dump() for evt in new_events],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("force_action failed game_id=%s", game_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{game_id}/players/{player_id}/knowledge")
def get_player_knowledge(game_id: str, player_id: str):
    """Get a player's knowledge context (beliefs, suspicions, plan)."""
    engine = _GAMES.get(game_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Game not found")

    try:
        # Normalize player_id
        player_id = player_id.strip().lower()

        # Get player
        player = engine.runtime.get_player(player_id)
        if player is None:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

        # Build observation to get full context
        observation = engine.observation_for(player_id)

        # Extract knowledge components
        return {
            "player_id": player_id,
            "role": observation.role.value,
            "alive": player.alive,
            "social_ap": player.social_ap,
            "social_ap_max": player.social_ap_max,
            "beliefs": {
                "suspicion": observation.private_memory.beliefs.suspicion,
                "top_suspects": observation.private_memory.beliefs.top_suspects,
                "trusted": observation.private_memory.beliefs.trusted,
            },
            "plan_next": observation.private_memory.plan_next,
            "controls": {
                "assertiveness": observation.controls.assertiveness,
                "skepticism": observation.controls.skepticism,
                "query_rate": observation.controls.query_rate,
                "risk": observation.controls.risk,
                "deception": observation.controls.deception,
                "verbosity": observation.controls.verbosity,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "get_player_knowledge failed game_id=%s player_id=%s", game_id, player_id
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{game_id}/players/{player_id}/chat")
def chat_with_player(game_id: str, player_id: str, payload: AIChatRequest):
    """Chat with a player's agent."""
    engine = _GAMES.get(game_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Game not found")

    agents = _AGENTS.get(game_id)
    if agents is None:
        raise HTTPException(status_code=404, detail="Game has no agents initialized")

    try:
        # Normalize player_id
        player_id = player_id.strip().lower()

        # Get agent
        agent = agents.get(player_id)
        if agent is None:
            raise HTTPException(
                status_code=404, detail=f"Agent for player {player_id} not found"
            )

        # Verify agent is an LLMAgent
        if not isinstance(agent, LLMAgent):
            raise HTTPException(
                status_code=400,
                detail=f"Player {player_id} is not an LLM agent (cannot chat)",
            )

        # Get observation for context
        observation = engine.observation_for(player_id)

        # Generate response using the agent's LLM client
        response = agent.client.generate_response(
            user_message=payload.message,
            observation=observation,
            system_prompt=agent.system_prompt,
        )

        logger.info(
            "chat_with_player game_id=%s player_id=%s message_len=%s response_len=%s",
            game_id,
            player_id,
            len(payload.message),
            len(response),
        )

        return {"ok": True, "response": response}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "chat_with_player failed game_id=%s player_id=%s", game_id, player_id
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{game_id}/preview-next")
def preview_next_action(game_id: str):
    """Preview who will act next without executing."""
    engine = _GAMES.get(game_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Game not found")

    agents = _AGENTS.get(game_id)
    if not agents:
        agents = {
            p.player_id: ScriptedAgent(seed=idx)
            for idx, p in enumerate(engine.runtime.public_state.players)
        }
        _AGENTS[game_id] = agents

    summary_agent = _SUMMARY_AGENTS.get(game_id)

    try:
        loop = GameLoop(engine, agents, summary_agent=summary_agent)
        preview = loop.preview_next_actor()
        return {"ok": True, "next_actor": preview}
    except Exception as exc:
        logger.exception("preview_next_action failed game_id=%s", game_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{game_id}/status")
def get_game_status(game_id: str):
    """Get current execution status for real-time UI updates."""
    engine = _GAMES.get(game_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Game not found")

    public_state = engine.runtime.public_state
    response = {
        "ok": True,
        "status": engine.runtime.execution_status.model_dump(),
        "phase": public_state.phase.value,
        "round_num": public_state.round_num,
    }

    # Include vote data during vote phase for real-time display
    if public_state.phase.value == "vote":
        # Get current votes and tally
        current_votes = public_state.current_votes
        vote_tally: dict[str, int] = {}
        for target in current_votes.values():
            vote_tally[target] = vote_tally.get(target, 0) + 1

        # Get alive players for context
        alive_players = [p.player_id for p in public_state.players if p.alive]
        total_voters = len(alive_players)
        votes_cast = len(current_votes)

        response["votes"] = {
            "current_votes": current_votes,  # voter_id -> target_id
            "vote_tally": vote_tally,  # target_id -> count
            "votes_cast": votes_cast,
            "total_voters": total_voters,
            "alive_players": alive_players,
        }

    return response


@router.get("/{game_id}/prompts/{request_id}")
def get_prompt(game_id: str, request_id: str):
    """Retrieve stored LLM prompt and response for debugging."""
    prompts = _PROMPT_STORE.get(game_id, {})
    prompt_data = prompts.get(request_id)

    if not prompt_data:
        raise HTTPException(status_code=404, detail="Prompt not found")

    return {
        "ok": True,
        "request_id": request_id,
        "prompt": prompt_data,
    }


class NarratorTextRequest(BaseModel):
    reason: str


@router.post("/{game_id}/generate-narrator-text")
async def generate_narrator_text(game_id: str, payload: NarratorTextRequest):
    """Generate narrator text for phase transitions or events."""
    engine = _GAMES.get(game_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Game not found")

    summary_agent = _SUMMARY_AGENTS.get(game_id)
    if summary_agent is None:
        raise HTTPException(
            status_code=400,
            detail="No summary agent available. Game must use 'ollama' agent type.",
        )

    try:
        runtime = engine.runtime
        reason = payload.reason

        # Build context based on reason
        if reason == "opening_body_event":
            context = "Generate a dramatic narrator message announcing that a body has been discovered at dawn. The town is shaken, but all players remain in the game."
        elif reason == "resolve_votes":
            context = "Generate a narrator message summarizing the voting results and announcing the outcome."
        elif reason == "phase_advance":
            phase = runtime.public_state.phase.value
            context = f"Generate a narrator message for transitioning from {phase} phase to the next phase."
        else:
            # General summary
            start_idx = runtime.last_summary_index
            events = runtime.event_history[start_idx:]
            public_events = [evt for evt in events if evt.visibility.mode == "public"]

            public_state_json = runtime.public_state.model_dump_json(indent=2)
            transcript_json = runtime.public_memory.model_dump_json(indent=2)
            events_json = (
                "[" + ", ".join(evt.model_dump_json() for evt in public_events) + "]"
                if public_events
                else "[]"
            )

            narrator_text = summary_agent.summarize(
                public_state_json, transcript_json, events_json
            ).strip()
            return {"ok": True, "narrator_text": narrator_text}

        # Use summary agent to generate context-based text
        response = await summary_agent.client.generate(
            system_prompt=summary_agent.system_prompt,
            user_prompt=context,
        )

        return {"ok": True, "narrator_text": response.strip()}
    except Exception as exc:
        logger.exception("generate_narrator_text failed game_id=%s", game_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
