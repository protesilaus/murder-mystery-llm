"""Baseline scripted bot for testing."""

from __future__ import annotations

from mmllm.agents.base import Agent
from mmllm.core.rng import RNG
from mmllm.core.types import (
    ActionRequest,
    ActionResponse,
    ActionType,
    AgentObservation,
    InvestigateAction,
    KillAction,
    PassAction,
    SpeakAction,
    VoteAction,
    Role,
)


class ScriptedAgent(Agent):
    def __init__(self, seed: int | None = None) -> None:
        self._rng = RNG(seed)
        self._last_observation: AgentObservation | None = None

    def observe(self, observation: AgentObservation) -> None:
        self._last_observation = observation

    def act(self, request: ActionRequest, observation: AgentObservation) -> ActionResponse:
        phase = observation.phase
        alive = [p.player_id for p in observation.public_state.players if p.alive]
        others = [pid for pid in alive if pid != observation.player_id]

        action: object
        if ActionType.kill in request.allowed_actions and observation.role == Role.murderer and others:
            target = self._rng.choice(others)
            action = KillAction(target_player_id=target)
        elif ActionType.investigate in request.allowed_actions and observation.role == Role.detective and others:
            target = self._rng.choice(others)
            action = InvestigateAction(target_player_id=target)
        elif ActionType.vote in request.allowed_actions and others:
            target = self._rng.choice(others)
            action = VoteAction(target_player_id=target)
        elif ActionType.speak in request.allowed_actions:
            action = SpeakAction(body=f"I am speaking during {phase.value}.")
        else:
            action = PassAction(note="No action.")

        return ActionResponse(
            request_id=request.request_id,
            game_id=request.game_id,
            player_id=request.player_id,
            round_num=request.round_num,
            phase=request.phase,
            action=action,
        )
