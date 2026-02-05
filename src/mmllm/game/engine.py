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

# Constants for prompt optimization
TRANSCRIPT_WINDOW_SIZE = 8  # Number of recent messages to include in prompts


def _sanitize_public_state_for_player(
    public_state: PublicState, player_id: str
) -> PublicState:
    """Create a sanitized copy of public_state for a specific player.

    Removes information that should be private:
    - Other players' personality controls (deception, risk, etc.)
    - Other players' social_ap (only show their own)
    """
    sanitized_players = []
    for player in public_state.players:
        if player.player_id == player_id:
            # Keep full info for the requesting player
            sanitized_players.append(player)
        else:
            # Sanitize other players - remove controls and AP info
            sanitized_players.append(
                PlayerState(
                    player_id=player.player_id,
                    alive=player.alive,
                    social_ap_max=0,  # Hidden from other players
                    social_ap=0,  # Hidden from other players
                    controls=Controls(),  # Default/neutral controls (hides personality)
                )
            )

    return PublicState(
        game_id=public_state.game_id,
        round_num=public_state.round_num,
        phase=public_state.phase,
        players=sanitized_players,
        last_night_kill=public_state.last_night_kill,
        last_day_eliminated=public_state.last_day_eliminated,
        current_votes=public_state.current_votes,
    )


def _window_transcript(
    public_memory: PublicMemory, window_size: int = TRANSCRIPT_WINDOW_SIZE
) -> PublicMemory:
    """Create a copy of public_memory with only the last N transcript entries.

    This reduces token usage in prompts while keeping recent context.
    """
    windowed_transcript = public_memory.transcript[-window_size:]

    return PublicMemory(
        transcript=windowed_transcript,
        event_digests=public_memory.event_digests,
        round_summaries=public_memory.round_summaries,
    )


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
                # LLM generation params for conversation diversity
                temperature=rng._random.uniform(0.5, 1.0),
                top_p=rng._random.uniform(0.8, 0.95),
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
            phase_list = []
            for p in self.game_config.phases:
                # Skip analysis phase if not enabled in special rules
                if (
                    p.name == "analysis"
                    and not self.game_config.special_rules.enable_analysis_phase
                ):
                    continue
                phase_list.append(Phase(p.name))
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

        # Sanitize public state to remove other players' private info
        sanitized_public_state = _sanitize_public_state_for_player(
            self.runtime.public_state, player_id
        )

        # Window the transcript to reduce token usage
        windowed_memory = _window_transcript(self.runtime.public_memory)

        return AgentObservation(
            game_id=self.runtime.public_state.game_id,
            player_id=player_id,
            round_num=self.runtime.public_state.round_num,
            phase=self.runtime.public_state.phase,
            public_state=sanitized_public_state,
            public_memory=windowed_memory,
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

        # Check for win conditions after elimination
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
