"""Summary agent for public narration."""

from __future__ import annotations

from mmllm.llm.client import LLMClient


class SummaryAgent:
    def __init__(self, client: LLMClient, system_prompt: str, user_prompt: str) -> None:
        self.client = client
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt

    def summarize(
        self, public_state_json: str, transcript_json: str, events_json: str
    ) -> str:
        return self.client.generate_summary(
            public_state_json,
            transcript_json,
            events_json,
            self.system_prompt,
            self.user_prompt,
        )
