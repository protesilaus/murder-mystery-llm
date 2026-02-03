"""Generic LLM-backed agent."""

from mmllm.agents.base import Agent
from mmllm.core.types import ActionRequest, ActionResponse, AgentObservation
from mmllm.llm.client import LLMClient


class LLMAgent(Agent):
    def __init__(self, client: LLMClient, system_prompt: str) -> None:
        self.client = client
        self.system_prompt = system_prompt

    def observe(self, observation: AgentObservation) -> None:
        self._last_observation = observation

    def act(self, request: ActionRequest, observation: AgentObservation) -> ActionResponse:
        return self.client.generate_action(request, observation, self.system_prompt)
