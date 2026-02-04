"""Prompt assembly utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml

from mmllm.core.types import ActionRequest, AgentObservation
from mmllm.llm.personality import get_personality_descriptors


@dataclass(frozen=True)
class GameConfig:
    player_count: int
    actions_per_player: int


@dataclass(frozen=True)
class PromptTemplates:
    system_town: str
    system_murderer: str
    system_detective: str
    action_speak: str
    action_vote: str
    action_kill: str
    action_investigate: str
    action_question: str
    action_poll: str
    action_whisper_send: str
    action_whisper_reply: str
    action_pass: str
    user: str
    summary_system: str
    summary_user: str
    memory_update_system: str
    memory_update_user: str
    party_name_system: str
    party_name_user: str


def _load_yaml(config_path: Path | None = None) -> dict:
    if config_path is None:
        config_path = Path.cwd() / "configs" / "prompts.yaml"

    if not config_path.exists():
        return {}

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def load_game_config(config_path: Path | None = None) -> GameConfig:
    data = _load_yaml(config_path)
    game = data.get("game", {}) if isinstance(data, dict) else {}
    player_count = int(game.get("player_count", 8) or 8)
    actions_per_player = int(game.get("actions_per_player", 3) or 3)
    return GameConfig(player_count=player_count, actions_per_player=actions_per_player)


def load_prompt_templates(config_path: Path | None = None) -> PromptTemplates:
    data = _load_yaml(config_path)
    if not data:
        return PromptTemplates(
            system_town="You are playing a Mafia-style social deduction game.",
            system_murderer="You are playing a Mafia-style social deduction game.",
            system_detective="You are playing a Mafia-style social deduction game.",
            action_speak="",
            action_vote="",
            action_kill="",
            action_investigate="",
            action_question="",
            action_poll="",
            action_whisper_send="",
            action_whisper_reply="",
            action_pass="",
            user="Phase: {phase}, Round: {round_num}.",
            summary_system="You are the public narrator for a Mafia-style deduction game.",
            summary_user="Summarize the most important public events so far.",
            memory_update_system="Update private beliefs for the player.",
            memory_update_user="Return JSON with suspicion_scores, top_suspects, trusted, plan_next.",
            party_name_system="You create display names for game agents.",
            party_name_user="Generate {count} display names for: {player_ids}. Return JSON array.",
        )
    prompts = data.get("prompts", {}) if isinstance(data, dict) else {}
    return PromptTemplates(
        system_town=str(prompts.get("system_town", "")),
        system_murderer=str(prompts.get("system_murderer", "")),
        system_detective=str(prompts.get("system_detective", "")),
        action_speak=str(prompts.get("action_speak", "")),
        action_vote=str(prompts.get("action_vote", "")),
        action_kill=str(prompts.get("action_kill", "")),
        action_investigate=str(prompts.get("action_investigate", "")),
        action_question=str(prompts.get("action_question", "")),
        action_poll=str(prompts.get("action_poll", "")),
        action_whisper_send=str(prompts.get("action_whisper_send", "")),
        action_whisper_reply=str(prompts.get("action_whisper_reply", "")),
        action_pass=str(prompts.get("action_pass", "")),
        user=str(prompts.get("user", "")),
        summary_system=str(prompts.get("summary_system", "")),
        summary_user=str(prompts.get("summary_user", "")),
        memory_update_system=str(prompts.get("memory_update_system", "")),
        memory_update_user=str(prompts.get("memory_update_user", "")),
        party_name_system=str(prompts.get("party_name_system", "")),
        party_name_user=str(prompts.get("party_name_user", "")),
    )


def _safe_format(template: str, format_args: Dict[str, object]) -> str:
    rendered = template
    for key, value in format_args.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def build_messages(
    request: ActionRequest,
    observation: AgentObservation,
    system_prompt: str,
    user_prompt: str,
    action_prompt: str | None = None,
) -> List[Dict[str, str]]:
    allowed_actions = [action.value for action in request.allowed_actions]
    action_request_json = json.dumps(request.model_dump(), ensure_ascii=False, indent=2)
    observation_json = json.dumps(
        observation.model_dump(), ensure_ascii=False, indent=2
    )
    constraints_json = json.dumps(
        request.constraints.model_dump(), ensure_ascii=False, indent=2
    )

    # Get personality descriptors from controls
    personality_descriptors = get_personality_descriptors(observation.controls)

    format_args = {
        "request_id": request.request_id,
        "player_id": request.player_id,
        "game_id": request.game_id,
        "round_num": request.round_num,
        "phase": request.phase.value,
        "role": observation.role.value,
        "ap_available": request.ap_available,
        "allowed_actions": ", ".join(allowed_actions),
        "action_request": action_request_json,
        "observation": observation_json,
        "constraints": constraints_json,
        # Add personality values
        "assertiveness": f"{observation.controls.assertiveness:.2f}",
        "skepticism": f"{observation.controls.skepticism:.2f}",
        "query_rate": f"{observation.controls.query_rate:.2f}",
        "risk": f"{observation.controls.risk:.2f}",
        "deception": f"{observation.controls.deception:.2f}",
        "verbosity": f"{observation.controls.verbosity:.2f}",
        # Add personality descriptions
        **personality_descriptors,
    }

    system_content = _safe_format(system_prompt, format_args)
    if action_prompt:
        action_content = _safe_format(action_prompt, format_args)
        if action_content.strip():
            system_content = f"{system_content}\n\n{action_content}"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": _safe_format(user_prompt, format_args)},
    ]


def build_summary_messages(
    public_state_json: str,
    transcript_json: str,
    events_json: str,
    system_prompt: str,
    user_prompt: str,
) -> List[Dict[str, str]]:
    format_args = {
        "public_state": public_state_json,
        "transcript": transcript_json,
        "events": events_json,
    }
    return [
        {"role": "system", "content": _safe_format(system_prompt, format_args)},
        {"role": "user", "content": _safe_format(user_prompt, format_args)},
    ]


def build_memory_update_messages(
    observation_json: str,
    transcript_json: str,
    system_prompt: str,
    user_prompt: str,
) -> List[Dict[str, str]]:
    format_args = {
        "observation": observation_json,
        "transcript": transcript_json,
    }
    return [
        {"role": "system", "content": _safe_format(system_prompt, format_args)},
        {"role": "user", "content": _safe_format(user_prompt, format_args)},
    ]


def build_party_name_messages(
    player_ids: List[str],
    system_prompt: str,
    user_prompt: str,
) -> List[Dict[str, str]]:
    format_args = {
        "count": len(player_ids),
        "player_ids": ", ".join(player_ids),
    }
    return [
        {"role": "system", "content": _safe_format(system_prompt, format_args)},
        {"role": "user", "content": _safe_format(user_prompt, format_args)},
    ]
