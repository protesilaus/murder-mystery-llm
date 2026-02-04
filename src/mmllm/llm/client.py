"""Abstract LLM client interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mmllm.core.types import ActionRequest, ActionResponse, AgentObservation


class LLMClient(ABC):
    @abstractmethod
    def generate_action(
        self,
        request: ActionRequest,
        observation: AgentObservation,
        system_prompt: str,
    ) -> ActionResponse:
        raise NotImplementedError

    def generate_summary(
        self,
        public_state_json: str,
        transcript_json: str,
        events_json: str,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
    ) -> str:
        raise NotImplementedError

    def generate_memory_update(
        self,
        observation_json: str,
        transcript_json: str,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
    ) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def generate_response(
        self,
        user_message: str,
        observation: AgentObservation,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a free-form text response to a user message with game context."""
        raise NotImplementedError
