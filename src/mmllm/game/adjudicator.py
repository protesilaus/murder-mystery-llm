"""Validates actions and applies outcomes."""

from __future__ import annotations

from typing import Callable, List

from mmllm.core.exceptions import ActionError, GameStateError, InvalidTargetError
from mmllm.core.game_config import GameTypeConfig
from mmllm.core.utils import event_id, ts_utc
from mmllm.core.types import (
    ActionResponse,
    ActionType,
    EventType,
    GameEvent,
    Phase,
    TranscriptEntry,
    Visibility,
)
from mmllm.game.rules import legal_actions
from mmllm.game.state import GameRuntime


def _action_cost(action_type: ActionType, config: GameTypeConfig | None = None) -> int:
    """Get the AP cost for an action from config or defaults."""
    if config is not None:
        return config.get_action_cost(action_type.value)
    # Fallback defaults for backward compatibility
    if action_type in (ActionType.question, ActionType.poll):
        return 2
    if action_type in (
        ActionType.speak,
        ActionType.whisper_send,
        ActionType.whisper_reply,
    ):
        return 1
    return 0


def _create_game_event(
    runtime: GameRuntime,
    event_type: EventType,
    *,
    actor_id: str | None = None,
    visibility: Visibility | None = None,
    payload: dict | None = None,
) -> GameEvent:
    """Create a GameEvent with common fields pre-filled from runtime."""
    return GameEvent(
        event_id=event_id("evt"),
        game_id=runtime.public_state.game_id,
        ts_utc=ts_utc(),
        event_type=event_type,
        round_num=runtime.public_state.round_num,
        phase=runtime.public_state.phase,
        actor_id=actor_id,
        visibility=visibility or Visibility(),
        payload=payload or {},
    )


def _create_transcript_entry(
    runtime: GameRuntime,
    speaker_id: str,
    body: str,
    visibility: Visibility | None = None,
) -> TranscriptEntry:
    """Create a TranscriptEntry with common fields pre-filled from runtime."""
    return TranscriptEntry(
        entry_id=event_id("entry"),
        round_num=runtime.public_state.round_num,
        phase=runtime.public_state.phase,
        speaker_id=speaker_id,
        body=body,
        visibility=visibility or Visibility(),
    )


# --- Action Handlers ---


def _handle_speak(runtime: GameRuntime, response: ActionResponse) -> List[GameEvent]:
    """Handle speak action."""
    action = response.action
    entry = _create_transcript_entry(runtime, response.player_id, action.body)
    runtime.public_memory.transcript.append(entry)
    return [
        _create_game_event(
            runtime,
            EventType.message_public,
            actor_id=response.player_id,
            payload={"body": action.body},
        )
    ]


def _handle_question(runtime: GameRuntime, response: ActionResponse) -> List[GameEvent]:
    """Handle question action."""
    action = response.action
    target = runtime.get_player(action.to_player_id)
    if target is None or not target.alive:
        raise InvalidTargetError(
            "invalid question target",
            target_id=action.to_player_id,
            player_id=response.player_id,
            action_type="question",
        )

    body = f"Question to {action.to_player_id}: {action.body}"
    entry = _create_transcript_entry(runtime, response.player_id, body)
    runtime.public_memory.transcript.append(entry)

    runtime.pending_question_from = response.player_id
    runtime.pending_question_to = action.to_player_id
    runtime.pending_question_body = action.body

    return [
        _create_game_event(
            runtime,
            EventType.message_public,
            actor_id=response.player_id,
            payload={
                "body": body,
                "to": action.to_player_id,
                "kind": "question",
            },
        )
    ]


def _handle_poll(runtime: GameRuntime, response: ActionResponse) -> List[GameEvent]:
    """Handle poll action."""
    action = response.action
    body = f"Poll: {action.body}"
    entry = _create_transcript_entry(runtime, response.player_id, body)
    runtime.public_memory.transcript.append(entry)

    return [
        _create_game_event(
            runtime,
            EventType.message_public,
            actor_id=response.player_id,
            payload={"body": body, "kind": "poll"},
        )
    ]


def _handle_investigate(
    runtime: GameRuntime, response: ActionResponse
) -> List[GameEvent]:
    """Handle investigate action."""
    action = response.action
    target = runtime.get_player(action.target_player_id)
    if target is None or not target.alive:
        raise InvalidTargetError(
            "invalid investigate target",
            target_id=action.target_player_id,
            player_id=response.player_id,
            action_type="investigate",
        )

    role = runtime.roles.get(action.target_player_id, None)
    config = runtime.game_config or GameTypeConfig.default_classic()
    investigator_role = runtime.roles.get(response.player_id)
    reveal_delay = config.get_investigation_delay(
        investigator_role.value if investigator_role else "detective"
    )

    runtime.pending_reveals.append(
        {
            "round_due": runtime.public_state.round_num + reveal_delay,
            "target_player_id": action.target_player_id,
            "role": role.value if role else "unknown",
        }
    )

    role_str = role.value if role else "unknown"
    body = f"Investigation result: {action.target_player_id} is {role_str}."
    visibility = Visibility(mode="direct", to=[response.player_id])
    entry = _create_transcript_entry(runtime, "narrator", body, visibility)

    detective_mem = runtime.private_memories.get(response.player_id)
    if detective_mem:
        detective_mem.private_messages.append(entry)

    return [
        _create_game_event(
            runtime,
            EventType.message_private,
            actor_id="narrator",
            visibility=visibility,
            payload={
                "body": body,
                "to": response.player_id,
                "kind": "investigation",
            },
        )
    ]


def _handle_whisper(runtime: GameRuntime, response: ActionResponse) -> List[GameEvent]:
    """Handle whisper_send and whisper_reply actions."""
    action = response.action
    visibility = Visibility(mode="direct", to=[response.player_id, action.to_player_id])
    entry = _create_transcript_entry(
        runtime, response.player_id, action.body, visibility
    )

    sender_mem = runtime.private_memories.get(response.player_id)
    receiver_mem = runtime.private_memories.get(action.to_player_id)
    if sender_mem:
        sender_mem.private_messages.append(entry)
    if receiver_mem:
        receiver_mem.private_messages.append(entry)

    return [
        _create_game_event(
            runtime,
            EventType.message_private,
            actor_id=response.player_id,
            visibility=visibility,
            payload={"body": action.body, "to": action.to_player_id},
        )
    ]


def _handle_vote(runtime: GameRuntime, response: ActionResponse) -> List[GameEvent]:
    """Handle vote action."""
    action = response.action
    runtime.public_state.current_votes[response.player_id] = action.target_player_id

    return [
        _create_game_event(
            runtime,
            EventType.vote_cast,
            actor_id=response.player_id,
            payload={"target": action.target_player_id},
        )
    ]


def _handle_kill(runtime: GameRuntime, response: ActionResponse) -> List[GameEvent]:
    """Handle kill action."""
    action = response.action
    target = runtime.get_player(action.target_player_id)
    if target is None or not target.alive:
        raise InvalidTargetError(
            "invalid kill target",
            target_id=action.target_player_id,
            player_id=response.player_id,
            action_type="kill",
        )

    target.alive = False
    runtime.public_state.last_night_kill = action.target_player_id
    runtime.eliminated_order.append(action.target_player_id)

    return [
        _create_game_event(
            runtime,
            EventType.night_kill,
            actor_id=response.player_id,
            payload={"target": action.target_player_id},
        ),
        _create_game_event(
            runtime,
            EventType.player_eliminated,
            actor_id=None,
            payload={"player_id": action.target_player_id},
        ),
    ]


def _handle_pass(runtime: GameRuntime, response: ActionResponse) -> List[GameEvent]:
    """Handle pass_turn action."""
    action = response.action
    return [
        _create_game_event(
            runtime,
            EventType.round_summary,
            actor_id=response.player_id,
            payload={"note": getattr(action, "note", None)},
        )
    ]


def _handle_analyze(runtime: GameRuntime, response: ActionResponse) -> List[GameEvent]:
    """Handle analyze action - update suspicion during analysis phase."""
    action = response.action

    # Update the player's private memory with new suspicion scores
    player_mem = runtime.private_memories.get(response.player_id)
    if player_mem and hasattr(action, "updated_suspicion"):
        # Merge new suspicion values into existing
        for target_id, score in action.updated_suspicion.items():
            player_mem.beliefs.suspicion[target_id] = score

        # Update top suspects based on new suspicion
        sorted_suspicion = sorted(
            player_mem.beliefs.suspicion.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        player_mem.beliefs.top_suspects = [pid for pid, _ in sorted_suspicion[:3]]

    # Record vote intention if provided (for analysis/debugging)
    vote_intention = getattr(action, "vote_intention", None)

    return [
        _create_game_event(
            runtime,
            EventType.memory_updated,
            actor_id=response.player_id,
            visibility=Visibility(mode="direct", to=[response.player_id]),
            payload={
                "updated_suspicion": getattr(action, "updated_suspicion", {}),
                "vote_intention": vote_intention,
            },
        )
    ]


# --- Action Dispatch Table ---

ActionHandler = Callable[[GameRuntime, ActionResponse], List[GameEvent]]

_ACTION_HANDLERS: dict[ActionType, ActionHandler] = {
    ActionType.speak: _handle_speak,
    ActionType.question: _handle_question,
    ActionType.poll: _handle_poll,
    ActionType.investigate: _handle_investigate,
    ActionType.whisper_send: _handle_whisper,
    ActionType.whisper_reply: _handle_whisper,
    ActionType.analyze: _handle_analyze,
    ActionType.vote: _handle_vote,
    ActionType.kill: _handle_kill,
    ActionType.pass_turn: _handle_pass,
}


# --- Main Entry Point ---


def apply_action(runtime: GameRuntime, response: ActionResponse) -> List[GameEvent]:
    """Validate and apply an action, returning the resulting game events."""
    # Validate game state matches
    if response.game_id != runtime.public_state.game_id:
        raise GameStateError(
            "action game_id does not match runtime",
            expected=runtime.public_state.game_id,
            actual=response.game_id,
        )
    if response.round_num != runtime.public_state.round_num:
        raise GameStateError(
            "action round_num does not match runtime",
            expected=str(runtime.public_state.round_num),
            actual=str(response.round_num),
        )
    if response.phase != runtime.public_state.phase:
        raise GameStateError(
            "action phase does not match runtime",
            expected=runtime.public_state.phase.value,
            actual=response.phase.value,
        )

    # Validate action is allowed
    allowed = legal_actions(runtime, response.player_id)
    if response.action.type not in allowed:
        raise ActionError(
            "action not allowed",
            player_id=response.player_id,
            action_type=response.action.type.value,
            game_id=response.game_id,
        )

    # Deduct AP cost during day phase (except for free replies and pass)
    action = response.action
    if runtime.public_state.phase == Phase.day and action.type != ActionType.pass_turn:
        if runtime.free_reply_player_id != response.player_id:
            player = runtime.get_player(response.player_id)
            if player:
                cost = _action_cost(action.type, runtime.game_config)
                player.social_ap = max(0, player.social_ap - cost)

    # Dispatch to appropriate handler
    handler = _ACTION_HANDLERS.get(action.type)
    if handler is None:
        raise ActionError(
            f"no handler for action type: {action.type.value}",
            player_id=response.player_id,
            action_type=action.type.value,
            game_id=response.game_id,
        )

    events = handler(runtime, response)
    runtime.event_history.extend(events)
    return events
