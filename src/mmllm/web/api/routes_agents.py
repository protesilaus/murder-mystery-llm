"""Agent routes."""

import json
from typing import Any, Dict
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field
from mmllm.llm.prompt_builder import load_prompt_templates

router = APIRouter()


class OllamaTestRequest(BaseModel):
    base_url: str = Field("http://127.0.0.1:11434")
    model: str = Field("llama3.1:8b")
    prompt: str = Field("Say hello in one sentence.")


class OllamaRawRequest(BaseModel):
    base_url: str = Field("http://127.0.0.1:11434")
    model: str = Field("llama3.1:8b")
    system_prompt: str = Field("", description="System prompt text")
    user_prompt: str = Field("", description="User prompt text")


@router.get("/")
def list_agents():
    return {"agents": []}


@router.get("/prompts")
def get_prompts():
    templates = load_prompt_templates()
    return {
        "system_town": templates.system_town,
        "system_murderer": templates.system_murderer,
        "system_detective": templates.system_detective,
        "system": templates.system_town,
        "action_speak": templates.action_speak,
        "action_vote": templates.action_vote,
        "action_kill": templates.action_kill,
        "action_investigate": templates.action_investigate,
        "action_question": templates.action_question,
        "action_poll": templates.action_poll,
        "action_whisper_send": templates.action_whisper_send,
        "action_whisper_reply": templates.action_whisper_reply,
        "action_pass": templates.action_pass,
        "user": templates.user,
        "summary_system": templates.summary_system,
        "summary_user": templates.summary_user,
        "memory_update_system": templates.memory_update_system,
        "memory_update_user": templates.memory_update_user,
    }


@router.post("/ollama/test")
def test_ollama(payload: OllamaTestRequest = Body(...)):
    url = f"{payload.base_url.rstrip('/')}/api/chat"
    body = {
        "model": payload.model,
        "stream": False,
        "messages": [
            {"role": "user", "content": payload.prompt},
        ],
    }
    try:
        response = _post_json(url, body)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    content = response.get("message", {}).get("content", "")
    return {"ok": True, "response": content, "raw": response}


@router.post("/ollama/raw")
def test_ollama_raw(payload: OllamaRawRequest = Body(...)):
    url = f"{payload.base_url.rstrip('/')}/api/chat"
    messages = []
    if payload.system_prompt:
        messages.append({"role": "system", "content": payload.system_prompt})
    if payload.user_prompt:
        messages.append({"role": "user", "content": payload.user_prompt})

    body = {
        "model": payload.model,
        "stream": False,
        "messages": messages,
    }

    try:
        response = _post_json(url, body)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    content = response.get("message", {}).get("content", "")
    return {"ok": True, "response": content, "raw": response}


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc
