"""Win conditions and legal actions."""

from typing import Iterable, List

from mmllm.core.types import ActionType, Phase, Role
from mmllm.game.state import GameRuntime


def is_game_over(runtime: GameRuntime) -> bool:
    return winner(runtime) is not None


def winner(runtime: GameRuntime) -> str | None:
    alive_ids = {p.player_id for p in runtime.public_state.players if p.alive}
    murderer_alive = runtime.murderer_id in alive_ids
    town_alive = alive_ids - {runtime.murderer_id}
    if not murderer_alive:
        return "town"
    if len(town_alive) <= 1:
        return "murderer"
    return None


def legal_actions(runtime: GameRuntime, player_id: str) -> List[ActionType]:
    player = runtime.get_player(player_id)
    if player is None or not player.alive:
        return []

    if runtime.pending_question_to == player_id and runtime.public_state.phase == Phase.day:
        return [ActionType.speak, ActionType.pass_turn]

    phase = runtime.public_state.phase
    if phase == Phase.night:
        role = runtime.roles.get(player_id)
        if role == Role.murderer:
            alive_town = [
                p.player_id
                for p in runtime.public_state.players
                if p.alive and p.player_id != runtime.murderer_id
            ]
            return [ActionType.kill, ActionType.pass_turn] if alive_town else [ActionType.pass_turn]
        if role == Role.detective:
            alive_others = [
                p.player_id for p in runtime.public_state.players if p.alive and p.player_id != player_id
            ]
            return [ActionType.investigate, ActionType.pass_turn] if alive_others else [ActionType.pass_turn]
    if phase == Phase.day:
        allowed: List[ActionType] = [ActionType.pass_turn]
        if player.social_ap >= 1:
            allowed.append(ActionType.speak)
        if player.social_ap >= 2:
            allowed.append(ActionType.question)
            allowed.append(ActionType.poll)
        return allowed
    if phase == Phase.vote:
        return [ActionType.vote, ActionType.pass_turn]
    return [ActionType.pass_turn]
