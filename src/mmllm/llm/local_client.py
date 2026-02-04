"""Local LLM client using Ollama."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict
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
        prompt_callback: Callable[[str, str, dict], None] | None = None,
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
        self.prompt_callback = prompt_callback

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

        # Store prompt before sending (if callback provided)
        if self.prompt_callback:
            prompt_data = {
                "request_id": request.request_id,
                "game_id": request.game_id,
                "player_id": request.player_id,
                "phase": request.phase.value,
                "round_num": request.round_num,
                "messages": messages,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.prompt_callback(request.game_id, request.request_id, prompt_data)

        payload = {
            "model": self.model,
            "stream": False,
            "messages": messages,
        }

        response = _post_json(f"{self.base_url}/api/chat", payload)
        content = response.get("message", {}).get("content", "")

        # Store response in prompt data (if callback provided)
        if self.prompt_callback:
            # Update with response
            prompt_data["response"] = {"content": content, "raw_response": response}
            self.prompt_callback(request.game_id, request.request_id, prompt_data)
        action, error, detected_type = _parse_action(content)
        
        # If parsing failed but we detected an action type, try a retry with corrective prompt
        if action is None and detected_type:
            retry_prompt = _build_retry_prompt(detected_type, request)
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": retry_prompt})
            retry_response = _post_json(f"{self.base_url}/api/chat", payload | {"messages": messages})
            retry_content = retry_response.get("message", {}).get("content", "")
            retry_action, retry_error, _ = _parse_action(retry_content)
            if retry_action is not None:
                return ActionResponse(
                    request_id=request.request_id,
                    game_id=request.game_id,
                    player_id=request.player_id,
                    round_num=request.round_num,
                    phase=request.phase,
                    action=retry_action,
                )
        
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

    def generate_response(
        self,
        user_message: str,
        observation: AgentObservation,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a free-form text response to a user message with game context."""
        # Use role-specific system prompt if not provided
        if system_prompt:
            role_system_prompt = system_prompt
        elif observation.role.value == "murderer":
            role_system_prompt = self.templates.system_murderer
        elif observation.role.value == "detective":
            role_system_prompt = self.templates.system_detective
        else:
            role_system_prompt = self.templates.system_town

        # Build messages with game context
        context_prompt = f"Current game context:\n{observation.model_dump_json(indent=2)}"
        messages = [
            {"role": "system", "content": role_system_prompt},
            {"role": "system", "content": context_prompt},
            {"role": "user", "content": user_message}
        ]

        payload = {
            "model": self.model,
            "stream": False,
            "messages": messages,
        }

        response = _post_json(f"{self.base_url}/api/chat", payload)
        return response.get("message", {}).get("content", "")


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
        return None, "empty_response", None

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"json_error line {exc.lineno} col {exc.colno}: {exc.msg}", None

    if not isinstance(data, dict):
        return None, "json_root_not_object", None

    # Try to extract the action block - support multiple formats
    action_block = None
    
    # Format 1: {"action": {"type": "...", ...}, ...}  (PREFERRED)
    if isinstance(data.get("action"), dict):
        action_block = data["action"]
    # Format 2: {"type": "...", ...} (legacy - action directly at root)
    elif "type" in data:
        action_block = data
    # Format 3: {"action": "speak", ...} (malformed - action is a string)
    elif "action" in data and isinstance(data["action"], str):
        # Try to reconstruct - assume the type is the action value
        action_block = {"type": data["action"]}
        # Copy over other fields that might be relevant
        for key in ["body", "target_player_id", "to_player_id", "note", "reasoning_private"]:
            if key in data:
                action_block[key] = data[key]
    
    if not isinstance(action_block, dict):
        keys = ", ".join(sorted(data.keys()))
        return None, f"missing action object (top-level keys: {keys})", None

    # Get action type - handle common variations
    action_type = action_block.get("type") or action_block.get("action_type") or action_block.get("action")
    
    if not action_type:
        keys = ", ".join(sorted(action_block.keys()))
        return None, f"missing type (keys: {keys}); raw={json.dumps(data)[:200]}", None
    
    # If action_type is a string, use it directly
    if not isinstance(action_type, str):
        return None, f"type must be string, got {type(action_type).__name__}", None

    try:
        action_enum = ActionType(action_type)
    except ValueError:
        allowed = ", ".join([t.value for t in ActionType])
        return None, f"unknown type '{action_type}' (allowed: {allowed})", None

    # Now we know the action type - use it for retries if needed
    detected_type = action_enum
    
    if action_enum == ActionType.speak:
        body = action_block.get("body")
        if body is None:
            return None, "missing body for speak", detected_type
        return SpeakAction(body=str(body)), None, None
    if action_enum == ActionType.question:
        to_player = action_block.get("to_player_id")
        body = action_block.get("body")
        if to_player is None or body is None:
            return None, "missing to_player_id/body for question", detected_type
        return (
            QuestionAction(
                to_player_id=str(to_player),
                body=str(body),
            ),
            None,
            None,
        )
    if action_enum == ActionType.poll:
        body = action_block.get("body")
        if body is None:
            return None, "missing body for poll", detected_type
        return PollAction(body=str(body)), None, None
    if action_enum == ActionType.investigate:
        target = action_block.get("target_player_id")
        if target is None:
            return None, "missing target_player_id for investigate", detected_type
        return InvestigateAction(target_player_id=str(target)), None, None
    if action_enum == ActionType.vote:
        target = action_block.get("target_player_id")
        if target is None:
            return None, "missing target_player_id for vote", detected_type
        return VoteAction(target_player_id=str(target)), None, None
    if action_enum == ActionType.kill:
        target = action_block.get("target_player_id")
        if target is None:
            return None, "missing target_player_id for kill", detected_type
        return KillAction(target_player_id=str(target)), None, None
    if action_enum == ActionType.whisper_send:
        to_player = action_block.get("to_player_id")
        body = action_block.get("body")
        if to_player is None or body is None:
            return None, "missing to_player_id/body for whisper_send", detected_type
        return (
            WhisperSendAction(
                to_player_id=str(to_player),
                body=str(body),
            ),
            None,
            None,
        )
    if action_enum == ActionType.whisper_reply:
        to_player = action_block.get("to_player_id")
        body = action_block.get("body")
        if to_player is None or body is None:
            return None, "missing to_player_id/body for whisper_reply", detected_type
        return (
            WhisperReplyAction(
                to_player_id=str(to_player),
                body=str(body),
            ),
            None,
            None,
        )
    return PassAction(note=str(action_block.get("note", ""))), None, None


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


def _build_retry_prompt(action_type: ActionType, request: ActionRequest) -> str:
    """Build a retry prompt when the first attempt had the right action type but was malformed."""
    
    templates = {
        ActionType.speak: {
            "template": '"request_id": REQID, "game_id": GAMEID, "player_id": PLAYERID, "round_num": ROUND, "phase": PHASE, "action": {"type": "speak", "body": "your message"}',
            "required": '"action": {"type": "speak", "body": "..."}',
            "missing": '"body" field',
        },
        ActionType.vote: {
            "template": '"request_id": REQID, "game_id": GAMEID, "player_id": PLAYERID, "round_num": ROUND, "phase": PHASE, "action": {"type": "vote", "target_player_id": "p3"}',
            "required": '"action": {"type": "vote", "target_player_id": "..."}',
            "missing": '"target_player_id" field',
        },
        ActionType.kill: {
            "template": '"request_id": REQID, "game_id": GAMEID, "player_id": PLAYERID, "round_num": ROUND, "phase": PHASE, "action": {"type": "kill", "target_player_id": "p3"}',
            "required": '"action": {"type": "kill", "target_player_id": "..."}',
            "missing": '"target_player_id" field',
        },
        ActionType.investigate: {
            "template": '"request_id": REQID, "game_id": GAMEID, "player_id": PLAYERID, "round_num": ROUND, "phase": PHASE, "action": {"type": "investigate", "target_player_id": "p3"}',
            "required": '"action": {"type": "investigate", "target_player_id": "..."}',
            "missing": '"target_player_id" field',
        },
        ActionType.question: {
            "template": '"request_id": REQID, "game_id": GAMEID, "player_id": PLAYERID, "round_num": ROUND, "phase": PHASE, "action": {"type": "question", "to_player_id": "p3", "body": "your question"}',
            "required": '"action": {"type": "question", "to_player_id": "...", "body": "..."}',
            "missing": '"to_player_id" or "body" field',
        },
        ActionType.poll: {
            "template": '"request_id": REQID, "game_id": GAMEID, "player_id": PLAYERID, "round_num": ROUND, "phase": PHASE, "action": {"type": "poll", "body": "your poll"}',
            "required": '"action": {"type": "poll", "body": "..."}',
            "missing": '"body" field',
        },
        ActionType.whisper_send: {
            "template": '"request_id": REQID, "game_id": GAMEID, "player_id": PLAYERID, "round_num": ROUND, "phase": PHASE, "action": {"type": "whisper_send", "to_player_id": "p3", "body": "your message"}',
            "required": '"action": {"type": "whisper_send", "to_player_id": "...", "body": "..."}',
            "missing": '"to_player_id" or "body" field',
        },
        ActionType.whisper_reply: {
            "template": '"request_id": REQID, "game_id": GAMEID, "player_id": PLAYERID, "round_num": ROUND, "phase": PHASE, "action": {"type": "whisper_reply", "to_player_id": "p3", "body": "your reply"}',
            "required": '"action": {"type": "whisper_reply", "to_player_id": "...", "body": "..."}',
            "missing": '"to_player_id" or "body" field',
        },
    }
    
    template = templates.get(action_type)
    if not template:
        return "Your last response had an invalid action type. Please try again with the correct structure."
    
    # Get phase string value
    phase_str = request.phase.value if hasattr(request.phase, 'value') else str(request.phase)
    
    example = (
        template["template"]
        .replace("REQID", f'"{request.request_id}"')
        .replace("GAMEID", f'"{request.game_id}"')
        .replace("PLAYERID", f'"{request.player_id}"')
        .replace("ROUND", str(request.round_num))
        .replace("PHASE", f'"{phase_str}"')
    )
    
    return (
        f"**RETRY**: Your last response detected a '{action_type.value}' action, but it was incomplete or malformed. "
        f"You are missing the {template['missing']}.\n\n"
        f"**Return EXACTLY this JSON structure:**\n"
        f"{{" + example + f', "suspicion_scores": {{}}}}\n\n'
        f"The 'action' field must include: {template['required']}\n"
        f"Reply with ONLY the corrected JSON, no other text."
    )
