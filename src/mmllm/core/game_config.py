"""Game type configuration models."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class TurnOrder(str, Enum):
    """How players are ordered within a phase."""

    sequential = "sequential"
    role_priority = "role_priority"
    random = "random"


class PhaseEndCondition(str, Enum):
    """When a phase ends."""

    all_acted = "all_acted"
    ap_exhausted_or_all_passed = "ap_exhausted_or_all_passed"
    votes_cast = "votes_cast"


class Team(str, Enum):
    """Team affiliations for win condition checking."""

    town = "town"
    mafia = "mafia"
    neutral = "neutral"


class WinConditionType(str, Enum):
    """Types of win conditions."""

    team_eliminated = "team_eliminated"
    role_eliminated = "role_eliminated"
    custom_count = "custom_count"


class PhaseConfig(BaseModel):
    """Configuration for a single phase."""

    name: str
    turn_order: TurnOrder = TurnOrder.sequential
    role_priority: List[str] = Field(default_factory=list)
    end_condition: PhaseEndCondition = PhaseEndCondition.all_acted
    ap_reset: bool = False


class AbilityConfig(BaseModel):
    """Configuration for a role ability."""

    action: str
    phase: str
    uses_per_round: int = 1
    reveal_delay: int = 0


class RoleConfig(BaseModel):
    """Configuration for a game role."""

    team: Team
    count: Union[int, Literal["auto", "remaining"]] = "remaining"
    abilities: List[AbilityConfig] = Field(default_factory=list)


class ActionConfig(BaseModel):
    """Configuration for an action type."""

    ap_cost: int = 0
    ap_threshold: int = 0
    phases: List[str] = Field(default_factory=list)


class WinCondition(BaseModel):
    """Configuration for a win condition."""

    winner: str
    condition_type: WinConditionType
    team: Optional[str] = None
    role: Optional[str] = None
    count_lte: Optional[int] = None


class PlayerSettings(BaseModel):
    """Player-related settings."""

    min_players: int = 6
    max_players: int = 12
    actions_per_player: int = 3


class SpecialRules(BaseModel):
    """Special game rules."""

    round_1_skip_kill: bool = True
    opening_body_event: bool = True
    investigation_reveal_delay: int = 2


class GameTypeConfig(BaseModel):
    """Complete game type configuration."""

    name: str
    version: str = "1.0"
    description: str = ""

    player_settings: PlayerSettings = Field(default_factory=PlayerSettings)
    phases: List[PhaseConfig] = Field(default_factory=list)
    roles: Dict[str, RoleConfig] = Field(default_factory=dict)
    actions: Dict[str, ActionConfig] = Field(default_factory=dict)
    win_conditions: List[WinCondition] = Field(default_factory=list)
    special_rules: SpecialRules = Field(default_factory=SpecialRules)

    def get_phase_config(self, phase_name: str) -> Optional[PhaseConfig]:
        """Get configuration for a specific phase by name."""
        for phase in self.phases:
            if phase.name == phase_name:
                return phase
        return None

    def get_action_cost(self, action_name: str) -> int:
        """Get the AP cost for an action."""
        if action_name in self.actions:
            return self.actions[action_name].ap_cost
        return 0

    def get_action_threshold(self, action_name: str) -> int:
        """Get the AP threshold required to use an action."""
        if action_name in self.actions:
            return self.actions[action_name].ap_threshold
        return 0

    def is_action_available_in_phase(self, action_name: str, phase_name: str) -> bool:
        """Check if an action is available in a given phase."""
        if action_name in self.actions:
            return phase_name in self.actions[action_name].phases
        return False

    def get_role_abilities(self, role_name: str, phase_name: str) -> List[str]:
        """Get abilities available to a role in a specific phase."""
        if role_name in self.roles:
            return [
                ability.action
                for ability in self.roles[role_name].abilities
                if ability.phase == phase_name
            ]
        return []

    def get_investigation_delay(self, role_name: str) -> int:
        """Get the investigation reveal delay for a role."""
        if role_name in self.roles:
            for ability in self.roles[role_name].abilities:
                if ability.action == "investigate":
                    return ability.reveal_delay
        return self.special_rules.investigation_reveal_delay

    @classmethod
    def default_classic(cls) -> "GameTypeConfig":
        """Return the default classic game configuration matching current behavior."""
        return cls(
            name="classic",
            version="1.0",
            description="Classic murder mystery with detective",
            player_settings=PlayerSettings(
                min_players=6,
                max_players=12,
                actions_per_player=3,
            ),
            phases=[
                PhaseConfig(
                    name="night",
                    turn_order=TurnOrder.role_priority,
                    role_priority=["detective", "murderer"],
                    end_condition=PhaseEndCondition.all_acted,
                ),
                PhaseConfig(
                    name="day",
                    turn_order=TurnOrder.sequential,
                    end_condition=PhaseEndCondition.ap_exhausted_or_all_passed,
                    ap_reset=True,
                ),
                PhaseConfig(
                    name="vote",
                    turn_order=TurnOrder.random,
                    end_condition=PhaseEndCondition.votes_cast,
                ),
            ],
            roles={
                "murderer": RoleConfig(
                    team=Team.mafia,
                    count=1,
                    abilities=[AbilityConfig(action="kill", phase="night")],
                ),
                "detective": RoleConfig(
                    team=Team.town,
                    count=1,
                    abilities=[
                        AbilityConfig(action="investigate", phase="night", reveal_delay=2)
                    ],
                ),
                "town": RoleConfig(
                    team=Team.town,
                    count="remaining",
                ),
            },
            actions={
                "speak": ActionConfig(ap_cost=1, ap_threshold=1, phases=["day"]),
                "question": ActionConfig(ap_cost=2, ap_threshold=2, phases=["day"]),
                "poll": ActionConfig(ap_cost=2, ap_threshold=2, phases=["day"]),
                "vote": ActionConfig(ap_cost=0, ap_threshold=0, phases=["vote"]),
                "kill": ActionConfig(ap_cost=0, ap_threshold=0, phases=["night"]),
                "investigate": ActionConfig(ap_cost=0, ap_threshold=0, phases=["night"]),
                "whisper_send": ActionConfig(ap_cost=1, ap_threshold=1, phases=["day"]),
                "whisper_reply": ActionConfig(ap_cost=1, ap_threshold=1, phases=["day"]),
                "pass": ActionConfig(ap_cost=0, ap_threshold=0, phases=["night", "day", "vote"]),
            },
            win_conditions=[
                WinCondition(
                    winner="town",
                    condition_type=WinConditionType.role_eliminated,
                    role="murderer",
                ),
                WinCondition(
                    winner="murderer",
                    condition_type=WinConditionType.custom_count,
                    team="town",
                    count_lte=1,
                ),
            ],
            special_rules=SpecialRules(
                round_1_skip_kill=True,
                opening_body_event=True,
                investigation_reveal_delay=2,
            ),
        )
