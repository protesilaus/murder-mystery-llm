"""Local LLM client using Ollama."""

from __future__ import annotations

import json
import re
from typing import Any, Dict
from urllib.error import URLError
from urllib.request import Request, urlopen

from mmllm.core.types import (
    ActionRequest,
    ActionResponse,
    ActionType,
    AgentObservation,
    KillAction,
    PassAction,
    PollAction,
    QuestionAction,
    InvestigateAction,
    SpeakAction,
    VoteAction,
    WhisperReplyAction,
    WhisperSendAction,
)
from mmllm.llm.client import LLMClient
from mmllm.llm.prompt_builder import (
    build_memory_update_messages,
    build_messages,
    build_summary_messages,
    load_prompt_templates,
)

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class LocalClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.templates = load_prompt_templates()
        self.system_prompt = system_prompt or self.templates.system_town
        self.user_prompt = user_prompt or self.templates.user
        self.summary_system = self.templates.summary_system
        self.summary_user = self.templates.summary_user
        self.memory_update_system = self.templates.memory_update_system
        self.memory_update_user = self.templates.memory_update_user

    def generate_action(
        self,
        request: ActionRequest,
        observation: AgentObservation,
        system_prompt: str,
    ) -> ActionResponse:
        if system_prompt:
            role_system_prompt = system_prompt
        elif observation.role.value == "murderer":
            role_system_prompt = self.templates.system_murderer
        elif observation.role.value == "detective":
            role_system_prompt = self.templates.system_detective
        else:
            role_system_prompt = self.templates.system_town
        action_prompt = _select_action_prompt(request, self.templates)
        messages = build_messages(
            request,
            observation,
            role_system_prompt,
            self.user_prompt,
            action_prompt,
        )
        payload = {
            "model": self.model,
            "stream": False,
            "messages": messages,
        }

        response = _post_json(f"{self.base_url}/api/chat", payload)
        content = response.get("message", {}).get("content", "")
        action, error = _parse_action(content)
        if action is None:
            reason = error or "unknown_error"
            action = PassAction(
                note=f"parse_failed: {reason}; raw={_truncate(content)}"
            )
        return ActionResponse(
            request_id=request.request_id,
            game_id=request.game_id,
            player_id=request.player_id,
            round_num=request.round_num,
            phase=request.phase,
            action=action,
        )

    def generate_summary(
        self,
        public_state_json: str,
        transcript_json: str,
        events_json: str,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
    ) -> str:
        messages = build_summary_messages(
            public_state_json,
            transcript_json,
            events_json,
            system_prompt or self.summary_system,
            user_prompt or self.summary_user,
        )
        payload = {
            "model": self.model,
            "stream": False,
            "messages": messages,
        }
        response = _post_json(f"{self.base_url}/api/chat", payload)
        return response.get("message", {}).get("content", "")

    def generate_memory_update(
        self,
        observation_json: str,
        transcript_json: str,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
    ) -> dict | None:
        messages = build_memory_update_messages(
            observation_json,
            transcript_json,
            system_prompt or self.memory_update_system,
            user_prompt or self.memory_update_user,
        )
        payload = {
            "model": self.model,
            "stream": False,
            "messages": messages,
        }
        response = _post_json(f"{self.base_url}/api/chat", payload)
        content = response.get("message", {}).get("content", "")
        return _parse_memory_update(content)


def _select_action_prompt(request: ActionRequest, templates) -> str | None:
    action_map = {
        ActionType.speak: templates.action_speak,
        ActionType.vote: templates.action_vote,
        ActionType.kill: templates.action_kill,
        ActionType.investigate: templates.action_investigate,
        ActionType.question: templates.action_question,
        ActionType.poll: templates.action_poll,
        ActionType.whisper_send: templates.action_whisper_send,
        ActionType.whisper_reply: templates.action_whisper_reply,
        ActionType.pass_turn: templates.action_pass,
    }

    allowed = list(request.allowed_actions)
    non_pass = [a for a in allowed if a != ActionType.pass_turn]
    if not non_pass:
        return action_map.get(ActionType.pass_turn)
    if len(non_pass) == 1:
        return action_map.get(non_pass[0])
    return None


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc


def _parse_action(content: str):
    text = content.strip()
    match = _CODE_FENCE_RE.search(text)
    if match:
        text = match.group(1).strip()

    if not text:
        return None, "empty_response"

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"json_error line {exc.lineno} col {exc.colno}: {exc.msg}"

    if not isinstance(data, dict):
        return None, "json_root_not_object"

    action_block = data.get("action") if isinstance(data.get("action"), dict) else data
    if not isinstance(action_block, dict):
        return None, "missing action object"

    action_type = action_block.get("action_type")
    if not action_type:
        keys = ", ".join(sorted(action_block.keys()))
        return None, f"missing action_type (keys: {keys})"

    try:
        action_enum = ActionType(action_type)
    except ValueError:
        allowed = ", ".join([t.value for t in ActionType])
        return None, f"unknown action_type {action_type} (allowed: {allowed})"

    if action_enum == ActionType.speak:
        body = action_block.get("body")
        if body is None:
            return None, "missing body for speak"
        return SpeakAction(body=str(body)), None
    if action_enum == ActionType.question:
        to_player = action_block.get("to_player_id")
        body = action_block.get("body")
        if to_player is None or body is None:
            return None, "missing to_player_id/body for question"
        return (
            QuestionAction(
                to_player_id=str(to_player),
                body=str(body),
            ),
            None,
        )
    if action_enum == ActionType.poll:
        body = action_block.get("body")
        if body is None:
            return None, "missing body for poll"
        return PollAction(body=str(body)), None
    if action_enum == ActionType.investigate:
        target = action_block.get("target_player_id")
        if target is None:
            return None, "missing target_player_id for investigate"
        return InvestigateAction(target_player_id=str(target)), None
    if action_enum == ActionType.vote:
        target = action_block.get("target_player_id")
        if target is None:
            return None, "missing target_player_id for vote"
        return VoteAction(target_player_id=str(target)), None
    if action_enum == ActionType.kill:
        target = action_block.get("target_player_id")
        if target is None:
            return None, "missing target_player_id for kill"
        return KillAction(target_player_id=str(target)), None
    if action_enum == ActionType.whisper_send:
        to_player = action_block.get("to_player_id")
        body = action_block.get("body")
        if to_player is None or body is None:
            return None, "missing to_player_id/body for whisper_send"
        return (
            WhisperSendAction(
                to_player_id=str(to_player),
                body=str(body),
            ),
            None,
        )
    if action_enum == ActionType.whisper_reply:
        to_player = action_block.get("to_player_id")
        body = action_block.get("body")
        if to_player is None or body is None:
            return None, "missing to_player_id/body for whisper_reply"
        return (
            WhisperReplyAction(
                to_player_id=str(to_player),
                body=str(body),
            ),
            None,
        )
    return PassAction(note=str(action_block.get("note", ""))), None


def _parse_memory_update(content: str) -> dict | None:
    text = content.strip()
    match = _CODE_FENCE_RE.search(text)
    if match:
        text = match.group(1).strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    allowed = {"suspicion_scores", "top_suspects", "trusted", "plan_next"}
    return {k: v for k, v in data.items() if k in allowed}


def _truncate(text: str, limit: int = 300) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}…"
