"""Authoritative game state and runtime helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Set

from mmllm.core.clock import PhaseClock
from mmllm.core.types import GameEvent, GameStatus, Phase, PlayerState, PrivateMemory, PublicMemory, PublicState, Role

if TYPE_CHECKING:
    from mmllm.core.game_config import GameTypeConfig


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
    clock: PhaseClock = field(default_factory=lambda: PhaseClock([Phase.night, Phase.day, Phase.vote]))
    turn_order: List[str] = field(default_factory=list)
    turn_index: int = 0
    turn_round: int = 0
    turn_phase: Phase = Phase.setup
    cycle_passes: Set[str] = field(default_factory=set)
    last_summary_index: int = 0
    pending_question_from: str | None = None
    pending_question_to: str | None = None
    pending_question_body: str | None = None
    free_reply_player_id: str | None = None
    pending_reveals: List[dict] = field(default_factory=list)
    night1_investigation_done: bool = False
    night1_body_emitted: bool = False
    game_config: GameTypeConfig | None = None
    execution_status: GameStatus = field(default_factory=GameStatus)

    def living_players(self) -> List[PlayerState]:
        return [p for p in self.public_state.players if p.alive]

    def get_player(self, player_id: str) -> PlayerState | None:
        for player in self.public_state.players:
            if player.player_id == player_id:
                return player
        return None
