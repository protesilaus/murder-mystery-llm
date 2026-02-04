"""Win conditions and legal actions."""

from __future__ import annotations

from typing import List

from mmllm.core.game_config import GameTypeConfig, WinConditionType
from mmllm.core.types import ActionType, Phase
from mmllm.game.state import GameRuntime


def is_game_over(runtime: GameRuntime) -> bool:
    """Check if the game has ended."""
    return winner(runtime) is not None


def winner(runtime: GameRuntime) -> str | None:
    """Determine the winner based on game state and config.

    Returns the winner team name or None if game continues.
    """
    config = runtime.game_config or GameTypeConfig.default_classic()

    alive_ids = {p.player_id for p in runtime.public_state.players if p.alive}

    for condition in config.win_conditions:
        if _check_win_condition(runtime, condition, alive_ids, config):
            return condition.winner

    return None


def _check_win_condition(
    runtime: GameRuntime,
    condition,
    alive_ids: set,
    config: GameTypeConfig,
) -> bool:
    """Check if a specific win condition is met."""
    if condition.condition_type == WinConditionType.role_eliminated:
        # Check if the specified role has been eliminated
        role_name = condition.role
        for player_id, role in runtime.roles.items():
            if role.value == role_name and player_id in alive_ids:
                return False  # Role is still alive
        # Check if the role existed at all
        for role in runtime.roles.values():
            if role.value == role_name:
                return True  # Role existed and is now eliminated
        return False

    if condition.condition_type == WinConditionType.team_eliminated:
        # Check if the specified team has been eliminated
        team_name = condition.team
        for player_id in alive_ids:
            role = runtime.roles.get(player_id)
            if role:
                role_config = config.roles.get(role.value)
                if role_config and role_config.team.value == team_name:
                    return False  # Team member still alive
        return True

    if condition.condition_type == WinConditionType.custom_count:
        # Check if team count is at or below threshold
        team_name = condition.team
        count_threshold = condition.count_lte or 0
        team_count = 0
        for player_id in alive_ids:
            role = runtime.roles.get(player_id)
            if role:
                role_config = config.roles.get(role.value)
                if role_config and role_config.team.value == team_name:
                    team_count += 1
        return team_count <= count_threshold

    return False


def legal_actions(runtime: GameRuntime, player_id: str) -> List[ActionType]:
    """Get legal actions for a player based on game state and config."""
    config = runtime.game_config or GameTypeConfig.default_classic()

    player = runtime.get_player(player_id)
    if player is None or not player.alive:
        return []

    # Special case: responding to a pending question
    if runtime.pending_question_to == player_id and runtime.public_state.phase == Phase.day:
        return [ActionType.speak, ActionType.pass_turn]

    phase = runtime.public_state.phase
    phase_name = phase.value
    role = runtime.roles.get(player_id)
    role_name = role.value if role else None

    allowed: List[ActionType] = []

    # Check each action from config
    for action_name, action_cfg in config.actions.items():
        # Skip if action not available in this phase
        if not config.is_action_available_in_phase(action_name, phase_name):
            continue

        # Check AP threshold
        if player.social_ap < action_cfg.ap_threshold:
            continue

        # Handle role-specific abilities (kill, investigate)
        if action_name in ("kill", "investigate"):
            if role_name is None:
                continue
            abilities = config.get_role_abilities(role_name, phase_name)
            if action_name not in abilities:
                continue

            # Additional checks for valid targets
            if action_name == "kill":
                alive_others = [
                    p.player_id
                    for p in runtime.public_state.players
                    if p.alive and p.player_id != player_id
                ]
                if not alive_others:
                    continue
            elif action_name == "investigate":
                alive_others = [
                    p.player_id
                    for p in runtime.public_state.players
                    if p.alive and p.player_id != player_id
                ]
                if not alive_others:
                    continue

        # Try to add the action
        try:
            action_type = ActionType(action_name)
            if action_type not in allowed:
                allowed.append(action_type)
        except ValueError:
            continue

    # Always ensure pass is available
    if ActionType.pass_turn not in allowed:
        allowed.append(ActionType.pass_turn)

    return allowed
