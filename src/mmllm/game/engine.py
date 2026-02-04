"""Phase orchestration and turn order."""

from __future__ import annotations

from copy import deepcopy
from typing import Iterable, List

from mmllm.core.clock import PhaseClock
from mmllm.core.game_config import GameTypeConfig
from mmllm.core.rng import RNG
from mmllm.core.utils import event_id, normalize_player_id, ts_utc
from mmllm.core.types import (
    ActionResponse,
    AgentObservation,
    Controls,
    EventType,
    GameEvent,
    Phase,
    PlayerState,
    PrivateMemory,
    PublicMemory,
    PublicState,
    Role,
    TranscriptEntry,
    Visibility,
)
from mmllm.game.adjudicator import apply_action
from mmllm.game.rules import is_game_over, winner
from mmllm.game.state import GameRuntime


class GameEngine:
    def __init__(
        self,
        game_id: str,
        player_ids: Iterable[str],
        *,
        murderer_id: str | None = None,
        actions_per_player: int | None = None,
        phases: Iterable[Phase] | None = None,
        game_config: GameTypeConfig | None = None,
    ) -> None:
        # Use provided config or default to classic
        self.game_config = game_config or GameTypeConfig.default_classic()

        # Get settings from config, with parameter overrides for backwards compatibility
        effective_actions_per_player = (
            actions_per_player
            if actions_per_player is not None
            else self.game_config.player_settings.actions_per_player
        )

        ids = [normalize_player_id(pid) for pid in player_ids]
        if not ids:
            raise ValueError("player_ids must be non-empty")

        murderer = normalize_player_id(murderer_id) if murderer_id else ids[0]
        if murderer not in ids:
            raise ValueError("murderer_id must be one of the player_ids")

        detective = next((pid for pid in ids if pid != murderer), None)

        # Generate random personality for each player
        rng = RNG()
        players = []
        for pid in ids:
            controls = Controls(
                assertiveness=rng._random.uniform(0.3, 0.9),
                skepticism=rng._random.uniform(0.3, 0.9),
                query_rate=rng._random.uniform(0.2, 0.8),
                risk=rng._random.uniform(0.2, 0.9),
                deception=rng._random.uniform(0.1, 0.8),
                verbosity=rng._random.uniform(0.3, 0.8),
            )
            players.append(
                PlayerState(
                    player_id=pid,
                    social_ap_max=effective_actions_per_player,
                    social_ap=effective_actions_per_player,
                    controls=controls,
                )
            )
        public_state = PublicState(game_id=game_id.strip().lower(), players=players)
        public_memory = PublicMemory()
        private_memories = {
            pid: PrivateMemory(player_id=pid, round_num=public_state.round_num)
            for pid in ids
        }
        roles = {}
        for pid in ids:
            if pid == murderer:
                roles[pid] = Role.murderer
            elif detective and pid == detective:
                roles[pid] = Role.detective
            else:
                roles[pid] = Role.town

        # Use phases from config if not explicitly provided
        if phases is not None:
            phase_list = list(phases)
        else:
            phase_list = [Phase(p.name) for p in self.game_config.phases]
        clock = PhaseClock(phase_list)

        self.runtime = GameRuntime(
            public_state=public_state,
            public_memory=public_memory,
            private_memories=private_memories,
            roles=roles,
            murderer_id=murderer,
            detective_id=detective,
            clock=clock,
            game_config=self.game_config,
        )
        self.actions_per_player = effective_actions_per_player
        self._initial_runtime = deepcopy(self.runtime)

    def _reset_runtime(self) -> None:
        self.runtime = deepcopy(self._initial_runtime)

    def _sync_clock(self) -> None:
        phase = self.runtime.public_state.phase
        if phase in self.runtime.clock.phases:
            self.runtime.clock.index = self.runtime.clock.phases.index(phase)
            self.runtime.clock.round = self.runtime.public_state.round_num

    def rebuild_from_events(self, events: List[GameEvent]) -> None:
        self._reset_runtime()
        for event in events:
            self._apply_event(event)
        self.runtime.event_history = list(events)
        self._sync_clock()

    def _apply_event(self, event: GameEvent) -> None:
        if event.event_type == EventType.phase_started:
            self.runtime.public_state.phase = event.phase
            self.runtime.public_state.round_num = event.round_num
            return

        if event.event_type == EventType.game_ended:
            self.runtime.public_state.phase = Phase.ended
            return

        if event.event_type == EventType.message_public:
            speaker_id = event.actor_id or "narrator"
            entry = TranscriptEntry(
                entry_id=event.event_id,
                round_num=event.round_num,
                phase=event.phase,
                speaker_id=speaker_id,
                body=str(event.payload.get("body", "")),
                visibility=event.visibility or Visibility(),
            )
            self.runtime.public_memory.transcript.append(entry)
            return

        if event.event_type == EventType.message_private:
            speaker_id = event.actor_id or "narrator"
            to_player = str(event.payload.get("to", ""))
            entry = TranscriptEntry(
                entry_id=event.event_id,
                round_num=event.round_num,
                phase=event.phase,
                speaker_id=speaker_id,
                body=str(event.payload.get("body", "")),
                visibility=event.visibility
                or Visibility(mode="direct", to=[speaker_id, to_player]),
            )
            sender_mem = self.runtime.private_memories.get(speaker_id)
            receiver_mem = self.runtime.private_memories.get(to_player)
            if sender_mem:
                sender_mem.private_messages.append(entry)
            if receiver_mem:
                receiver_mem.private_messages.append(entry)
            return

        if event.event_type == EventType.vote_cast:
            if event.actor_id and "target" in event.payload:
                self.runtime.public_state.current_votes[event.actor_id] = str(
                    event.payload.get("target", "")
                )
            return

        if event.event_type == EventType.vote_resolved:
            eliminated = str(event.payload.get("eliminated", ""))
            if eliminated:
                self.runtime.public_state.last_day_eliminated = eliminated
                target = self.runtime.get_player(eliminated)
                if target:
                    target.alive = False
                if eliminated not in self.runtime.eliminated_order:
                    self.runtime.eliminated_order.append(eliminated)
            self.runtime.public_state.current_votes.clear()
            return

        if event.event_type == EventType.night_kill:
            target_id = str(event.payload.get("target", ""))
            if target_id:
                self.runtime.public_state.last_night_kill = target_id
                target = self.runtime.get_player(target_id)
                if target:
                    target.alive = False
                if target_id not in self.runtime.eliminated_order:
                    self.runtime.eliminated_order.append(target_id)
            return

        if event.event_type == EventType.player_eliminated:
            player_id = str(event.payload.get("player_id", ""))
            if player_id:
                target = self.runtime.get_player(player_id)
                if target:
                    target.alive = False
                if player_id not in self.runtime.eliminated_order:
                    self.runtime.eliminated_order.append(player_id)
            return

    def current_phase(self) -> Phase:
        return self.runtime.public_state.phase

    def start(self) -> List[GameEvent]:
        events: List[GameEvent] = [
            GameEvent(
                event_id=event_id("evt"),
                game_id=self.runtime.public_state.game_id,
                ts_utc=ts_utc(),
                event_type=EventType.game_created,
                round_num=self.runtime.public_state.round_num,
                phase=self.runtime.public_state.phase,
            )
        ]
        self.runtime.public_state.phase = self.runtime.clock.current()
        events.append(
            GameEvent(
                event_id=event_id("evt"),
                game_id=self.runtime.public_state.game_id,
                ts_utc=ts_utc(),
                event_type=EventType.phase_started,
                round_num=self.runtime.public_state.round_num,
                phase=self.runtime.public_state.phase,
                payload={"phase": self.runtime.public_state.phase.value},
            )
        )
        self.runtime.event_history.extend(events)
        return events

    def observation_for(self, player_id: str) -> AgentObservation:
        player_id = player_id.strip().lower()
        role = self.runtime.roles.get(player_id)
        memory = self.runtime.private_memories.get(player_id)
        player = self.runtime.get_player(player_id)
        if role is None or memory is None or player is None:
            raise ValueError("unknown player_id")

        return AgentObservation(
            game_id=self.runtime.public_state.game_id,
            player_id=player_id,
            round_num=self.runtime.public_state.round_num,
            phase=self.runtime.public_state.phase,
            public_state=self.runtime.public_state,
            public_memory=self.runtime.public_memory,
            role=role,
            private_memory=memory,
            controls=player.controls,
        )

    def advance_phase(self) -> List[GameEvent]:
        self.runtime.public_state.phase = self.runtime.clock.advance()
        self.runtime.public_state.round_num = self.runtime.clock.round
        for memory in self.runtime.private_memories.values():
            memory.round_num = self.runtime.public_state.round_num

        # Check if current phase should reset AP (from config or default day phase behavior)
        phase_name = self.runtime.public_state.phase.value
        phase_config = self.game_config.get_phase_config(phase_name)
        should_reset_ap = (phase_config and phase_config.ap_reset) or (
            phase_config is None and self.runtime.public_state.phase == Phase.day
        )
        if should_reset_ap:
            for player in self.runtime.public_state.players:
                player.social_ap_max = self.actions_per_player
                player.social_ap = self.actions_per_player

        events = [
            GameEvent(
                event_id=event_id("evt"),
                game_id=self.runtime.public_state.game_id,
                ts_utc=ts_utc(),
                event_type=EventType.phase_started,
                round_num=self.runtime.public_state.round_num,
                phase=self.runtime.public_state.phase,
                payload={"phase": self.runtime.public_state.phase.value},
            )
        ]
        self.runtime.event_history.extend(events)
        return events

    def apply_action(self, response: ActionResponse) -> List[GameEvent]:
        events = apply_action(self.runtime, response)
        if is_game_over(self.runtime):
            self.runtime.public_state.phase = Phase.ended
            events.append(
                GameEvent(
                    event_id=event_id("evt"),
                    game_id=self.runtime.public_state.game_id,
                    ts_utc=ts_utc(),
                    event_type=EventType.game_ended,
                    round_num=self.runtime.public_state.round_num,
                    phase=self.runtime.public_state.phase,
                    payload={"winner": winner(self.runtime)},
                )
            )
            self.runtime.event_history.extend(events)
        return events

    def resolve_votes(self) -> List[GameEvent]:
        if self.runtime.public_state.phase != Phase.vote:
            return []

        tally: dict[str, int] = {}
        for target in self.runtime.public_state.current_votes.values():
            tally[target] = tally.get(target, 0) + 1

        if not tally:
            self.runtime.public_state.current_votes.clear()
            return []

        target_id = sorted(tally.items(), key=lambda item: (-item[1], item[0]))[0][0]
        target = self.runtime.get_player(target_id)
        if target and target.alive:
            target.alive = False
            self.runtime.public_state.last_day_eliminated = target_id
            self.runtime.eliminated_order.append(target_id)

        self.runtime.public_state.current_votes.clear()
        events = [
            GameEvent(
                event_id=event_id("evt"),
                game_id=self.runtime.public_state.game_id,
                ts_utc=ts_utc(),
                event_type=EventType.vote_resolved,
                round_num=self.runtime.public_state.round_num,
                phase=self.runtime.public_state.phase,
                payload={"eliminated": target_id},
            )
        ]
        if target and target.alive is False:
            events.append(
                GameEvent(
                    event_id=event_id("evt"),
                    game_id=self.runtime.public_state.game_id,
                    ts_utc=ts_utc(),
                    event_type=EventType.player_eliminated,
                    round_num=self.runtime.public_state.round_num,
                    phase=self.runtime.public_state.phase,
                    payload={"player_id": target_id},
                )
            )
        self.runtime.event_history.extend(events)
        return events
