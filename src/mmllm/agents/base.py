"""Agent interface definition."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mmllm.core.types import ActionRequest, ActionResponse, AgentObservation


class Agent(ABC):
    """Base agent interface."""

    @abstractmethod
    def observe(self, observation: AgentObservation) -> None:  # pragma: no cover - interface only
        raise NotImplementedError

    @abstractmethod
    def act(
        self,
        request: ActionRequest,
        observation: AgentObservation,
    ) -> ActionResponse:  # pragma: no cover - interface only
        raise NotImplementedError
