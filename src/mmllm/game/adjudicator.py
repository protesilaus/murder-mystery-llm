"""Validates actions and applies outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from uuid import uuid4

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


def _ts_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def _action_cost(action_type: ActionType) -> int:
    if action_type in (ActionType.question, ActionType.poll):
        return 2
    if action_type in (ActionType.speak, ActionType.whisper_send, ActionType.whisper_reply):
        return 1
    return 0


def apply_action(runtime: GameRuntime, response: ActionResponse) -> List[GameEvent]:
    if response.game_id != runtime.public_state.game_id:
        raise ValueError("action game_id does not match runtime")
    if response.round_num != runtime.public_state.round_num:
        raise ValueError("action round_num does not match runtime")
    if response.phase != runtime.public_state.phase:
        raise ValueError("action phase does not match runtime")

    allowed = legal_actions(runtime, response.player_id)
    if response.action.action_type not in allowed:
        raise ValueError("action not allowed")

    events: List[GameEvent] = []
    action = response.action

    if runtime.public_state.phase == Phase.day and action.action_type != ActionType.pass_turn:
        if runtime.free_reply_player_id != response.player_id:
            player = runtime.get_player(response.player_id)
            if player:
                cost = _action_cost(action.action_type)
                player.social_ap = max(0, player.social_ap - cost)

    if action.action_type == ActionType.speak:
        entry = TranscriptEntry(
            entry_id=_event_id("entry"),
            round_num=runtime.public_state.round_num,
            phase=runtime.public_state.phase,
            speaker_id=response.player_id,
            body=action.body,
            visibility=Visibility(),
        )
        runtime.public_memory.transcript.append(entry)
        events.append(
            GameEvent(
                event_id=_event_id("evt"),
                game_id=runtime.public_state.game_id,
                ts_utc=_ts_utc(),
                event_type=EventType.message_public,
                round_num=runtime.public_state.round_num,
                phase=runtime.public_state.phase,
                actor_id=response.player_id,
                payload={"body": action.body},
            )
        )
    elif action.action_type == ActionType.question:
        target = runtime.get_player(action.to_player_id)
        if target is None or not target.alive:
            raise ValueError("invalid question target")
        entry = TranscriptEntry(
            entry_id=_event_id("entry"),
            round_num=runtime.public_state.round_num,
            phase=runtime.public_state.phase,
            speaker_id=response.player_id,
            body=f"Question to {action.to_player_id}: {action.body}",
            visibility=Visibility(),
        )
        runtime.public_memory.transcript.append(entry)
        runtime.pending_question_from = response.player_id
        runtime.pending_question_to = action.to_player_id
        runtime.pending_question_body = action.body
        events.append(
            GameEvent(
                event_id=_event_id("evt"),
                game_id=runtime.public_state.game_id,
                ts_utc=_ts_utc(),
                event_type=EventType.message_public,
                round_num=runtime.public_state.round_num,
                phase=runtime.public_state.phase,
                actor_id=response.player_id,
                payload={
                    "body": f"Question to {action.to_player_id}: {action.body}",
                    "to": action.to_player_id,
                    "kind": "question",
                },
            )
        )
    elif action.action_type == ActionType.poll:
        entry = TranscriptEntry(
            entry_id=_event_id("entry"),
            round_num=runtime.public_state.round_num,
            phase=runtime.public_state.phase,
            speaker_id=response.player_id,
            body=f"Poll: {action.body}",
            visibility=Visibility(),
        )
        runtime.public_memory.transcript.append(entry)
        events.append(
            GameEvent(
                event_id=_event_id("evt"),
                game_id=runtime.public_state.game_id,
                ts_utc=_ts_utc(),
                event_type=EventType.message_public,
                round_num=runtime.public_state.round_num,
                phase=runtime.public_state.phase,
                actor_id=response.player_id,
                payload={
                    "body": f"Poll: {action.body}",
                    "kind": "poll",
                },
            )
        )
    elif action.action_type == ActionType.investigate:
        target = runtime.get_player(action.target_player_id)
        if target is None or not target.alive:
            raise ValueError("invalid investigate target")
        role = runtime.roles.get(action.target_player_id, None)
        runtime.pending_reveals.append(
            {
                "round_due": runtime.public_state.round_num + 2,
                "target_player_id": action.target_player_id,
                "role": role.value if role else "unknown",
            }
        )
        entry = TranscriptEntry(
            entry_id=_event_id("entry"),
            round_num=runtime.public_state.round_num,
            phase=runtime.public_state.phase,
            speaker_id="narrator",
            body=f"Investigation result: {action.target_player_id} is {role.value if role else 'unknown'}.",
            visibility=Visibility(mode="direct", to=[response.player_id]),
        )
        detective_mem = runtime.private_memories.get(response.player_id)
        if detective_mem:
            detective_mem.private_messages.append(entry)
        events.append(
            GameEvent(
                event_id=_event_id("evt"),
                game_id=runtime.public_state.game_id,
                ts_utc=_ts_utc(),
                event_type=EventType.message_private,
                round_num=runtime.public_state.round_num,
                phase=runtime.public_state.phase,
                actor_id="narrator",
                visibility=Visibility(mode="direct", to=[response.player_id]),
                payload={
                    "body": f"Investigation result: {action.target_player_id} is {role.value if role else 'unknown'}.",
                    "to": response.player_id,
                    "kind": "investigation",
                },
            )
        )
    elif action.action_type in (ActionType.whisper_send, ActionType.whisper_reply):
        entry = TranscriptEntry(
            entry_id=_event_id("entry"),
            round_num=runtime.public_state.round_num,
            phase=runtime.public_state.phase,
            speaker_id=response.player_id,
            body=action.body,
            visibility=Visibility(mode="direct", to=[response.player_id, action.to_player_id]),
        )
        sender_mem = runtime.private_memories.get(response.player_id)
        receiver_mem = runtime.private_memories.get(action.to_player_id)
        if sender_mem:
            sender_mem.private_messages.append(entry)
        if receiver_mem:
            receiver_mem.private_messages.append(entry)
        events.append(
            GameEvent(
                event_id=_event_id("evt"),
                game_id=runtime.public_state.game_id,
                ts_utc=_ts_utc(),
                event_type=EventType.message_private,
                round_num=runtime.public_state.round_num,
                phase=runtime.public_state.phase,
                actor_id=response.player_id,
                visibility=Visibility(mode="direct", to=[response.player_id, action.to_player_id]),
                payload={"body": action.body, "to": action.to_player_id},
            )
        )
    elif action.action_type == ActionType.vote:
        runtime.public_state.current_votes[response.player_id] = action.target_player_id
        events.append(
            GameEvent(
                event_id=_event_id("evt"),
                game_id=runtime.public_state.game_id,
                ts_utc=_ts_utc(),
                event_type=EventType.vote_cast,
                round_num=runtime.public_state.round_num,
                phase=runtime.public_state.phase,
                actor_id=response.player_id,
                payload={"target": action.target_player_id},
            )
        )
    elif action.action_type == ActionType.kill:
        target = runtime.get_player(action.target_player_id)
        if target is None or not target.alive:
            raise ValueError("invalid kill target")
        target.alive = False
        runtime.public_state.last_night_kill = action.target_player_id
        runtime.eliminated_order.append(action.target_player_id)
        events.append(
            GameEvent(
                event_id=_event_id("evt"),
                game_id=runtime.public_state.game_id,
                ts_utc=_ts_utc(),
                event_type=EventType.night_kill,
                round_num=runtime.public_state.round_num,
                phase=runtime.public_state.phase,
                actor_id=response.player_id,
                payload={"target": action.target_player_id},
            )
        )
        events.append(
            GameEvent(
                event_id=_event_id("evt"),
                game_id=runtime.public_state.game_id,
                ts_utc=_ts_utc(),
                event_type=EventType.player_eliminated,
                round_num=runtime.public_state.round_num,
                phase=runtime.public_state.phase,
                actor_id=None,
                payload={"player_id": action.target_player_id},
            )
        )
    elif action.action_type == ActionType.pass_turn:
        events.append(
            GameEvent(
                event_id=_event_id("evt"),
                game_id=runtime.public_state.game_id,
                ts_utc=_ts_utc(),
                event_type=EventType.round_summary,
                round_num=runtime.public_state.round_num,
                phase=runtime.public_state.phase,
                actor_id=response.player_id,
                payload={"note": getattr(action, "note", None)},
            )
        )

    runtime.event_history.extend(events)
    return events
