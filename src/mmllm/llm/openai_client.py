"""OpenAI client placeholder."""

from mmllm.core.types import ActionRequest, ActionResponse, AgentObservation, PassAction
from mmllm.llm.client import LLMClient


class OpenAIClient(LLMClient):
    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        self.model = model

    def generate_action(
        self,
        request: ActionRequest,
        observation: AgentObservation,
        system_prompt: str,
    ) -> ActionResponse:
        action = PassAction(note=f"model={self.model}")
        return ActionResponse(
            request_id=request.request_id,
            game_id=request.game_id,
            player_id=request.player_id,
            round_num=request.round_num,
            phase=request.phase,
            action=action,
        )
