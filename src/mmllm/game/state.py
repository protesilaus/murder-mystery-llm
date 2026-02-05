"""Authoritative game state and runtime helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Set

from mmllm.core.clock import PhaseClock
from mmllm.core.types import (
    GameEvent,
    GameStatus,
    Phase,
    PlayerState,
    PrivateMemory,
    PublicMemory,
    PublicState,
    Role,
)

if TYPE_CHECKING:
    from mmllm.core.game_config import GameTypeConfig


@dataclass
class PendingQuestion:
    """Tracks a pending question that requires a response."""

    from_player_id: str
    to_player_id: str
    body: str


@dataclass
class Night1State:
    """Tracks special state for round 1 night phase."""

    investigation_done: bool = False
    body_emitted: bool = False


@dataclass
class TurnState:
    """Tracks turn order and cycling within a phase."""

    order: List[str] = field(default_factory=list)
    index: int = 0
    round_num: int = 0
    phase: Phase = Phase.setup
    cycle_passes: Set[str] = field(default_factory=set)


@dataclass
class GameRuntime:
    public_state: PublicState
    public_memory: PublicMemory
    private_memories: Dict[str, PrivateMemory]
    roles: Dict[str, Role]
    murderer_id: str
    detective_id: str | None = None
    eliminated_order: List[str] = field(default_factory=list)
    event_history: List[GameEvent] = field(default_factory=list)
    clock: PhaseClock = field(
        default_factory=lambda: PhaseClock([Phase.night, Phase.day, Phase.vote])
    )
    last_summary_index: int = 0
    pending_reveals: List[dict] = field(default_factory=list)
    game_config: GameTypeConfig | None = None
    execution_status: GameStatus = field(default_factory=GameStatus)

    # Grouped state fields
    turn_state: TurnState = field(default_factory=TurnState)
    night1: Night1State = field(default_factory=Night1State)
    pending_question: PendingQuestion | None = None
    free_reply_player_id: str | None = None

    # Legacy properties for backward compatibility
    @property
    def turn_order(self) -> List[str]:
        return self.turn_state.order

    @turn_order.setter
    def turn_order(self, value: List[str]) -> None:
        self.turn_state.order = value

    @property
    def turn_index(self) -> int:
        return self.turn_state.index

    @turn_index.setter
    def turn_index(self, value: int) -> None:
        self.turn_state.index = value

    @property
    def turn_round(self) -> int:
        return self.turn_state.round_num

    @turn_round.setter
    def turn_round(self, value: int) -> None:
        self.turn_state.round_num = value

    @property
    def turn_phase(self) -> Phase:
        return self.turn_state.phase

    @turn_phase.setter
    def turn_phase(self, value: Phase) -> None:
        self.turn_state.phase = value

    @property
    def cycle_passes(self) -> Set[str]:
        return self.turn_state.cycle_passes

    @cycle_passes.setter
    def cycle_passes(self, value: Set[str]) -> None:
        self.turn_state.cycle_passes = value

    @property
    def night1_investigation_done(self) -> bool:
        return self.night1.investigation_done

    @night1_investigation_done.setter
    def night1_investigation_done(self, value: bool) -> None:
        self.night1.investigation_done = value

    @property
    def night1_body_emitted(self) -> bool:
        return self.night1.body_emitted

    @night1_body_emitted.setter
    def night1_body_emitted(self, value: bool) -> None:
        self.night1.body_emitted = value

    @property
    def pending_question_from(self) -> str | None:
        return self.pending_question.from_player_id if self.pending_question else None

    @pending_question_from.setter
    def pending_question_from(self, value: str | None) -> None:
        if value is None:
            self.pending_question = None
        elif self.pending_question:
            self.pending_question = PendingQuestion(
                from_player_id=value,
                to_player_id=self.pending_question.to_player_id,
                body=self.pending_question.body,
            )
        else:
            # Create a placeholder - will be filled in by subsequent setters
            self.pending_question = PendingQuestion(
                from_player_id=value, to_player_id="", body=""
            )

    @property
    def pending_question_to(self) -> str | None:
        return self.pending_question.to_player_id if self.pending_question else None

    @pending_question_to.setter
    def pending_question_to(self, value: str | None) -> None:
        if value is None:
            self.pending_question = None
        elif self.pending_question:
            self.pending_question = PendingQuestion(
                from_player_id=self.pending_question.from_player_id,
                to_player_id=value,
                body=self.pending_question.body,
            )
        else:
            self.pending_question = PendingQuestion(
                from_player_id="", to_player_id=value, body=""
            )

    @property
    def pending_question_body(self) -> str | None:
        return self.pending_question.body if self.pending_question else None

    @pending_question_body.setter
    def pending_question_body(self, value: str | None) -> None:
        if value is None:
            self.pending_question = None
        elif self.pending_question:
            self.pending_question = PendingQuestion(
                from_player_id=self.pending_question.from_player_id,
                to_player_id=self.pending_question.to_player_id,
                body=value,
            )
        else:
            self.pending_question = PendingQuestion(
                from_player_id="", to_player_id="", body=value
            )

    def living_players(self) -> List[PlayerState]:
        return [p for p in self.public_state.players if p.alive]

    def get_player(self, player_id: str) -> PlayerState | None:
        for player in self.public_state.players:
            if player.player_id == player_id:
                return player
        return None
