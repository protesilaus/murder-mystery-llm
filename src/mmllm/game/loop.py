"""Gameplay loop orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, List
from uuid import uuid4

from mmllm.agents.base import Agent
from mmllm.core.rng import RNG

from mmllm.core.types import (
    ActionRequest,
    ActionResponse,
    ActionType,
    EventType,
    GameEvent,
    Phase,
    Visibility,
)
from mmllm.game.rules import legal_actions
from mmllm.game.engine import GameEngine
from mmllm.agents.summary_agent import SummaryAgent


class GameLoop:
    def __init__(
        self,
        engine: GameEngine,
        agents: Dict[str, Agent],
        *,
        seed: int | None = None,
        summary_agent: SummaryAgent | None = None,
    ) -> None:
        self.engine = engine
        self.agents = agents
        self.rng = RNG(seed)
        self.summary_agent = summary_agent

    def _request_for(self, player_id: str) -> ActionRequest:
        allowed = legal_actions(self.engine.runtime, player_id)
        player = self.engine.runtime.get_player(player_id)
        ap_available = player.social_ap if player else 0
        return ActionRequest(
            request_id=f"req_{uuid4().hex[:8]}",
            game_id=self.engine.runtime.public_state.game_id,
            player_id=player_id,
            round_num=self.engine.runtime.public_state.round_num,
            phase=self.engine.runtime.public_state.phase,
            allowed_actions=allowed,
            ap_available=ap_available,
        )

    def _turn_order(self) -> List[str]:
        alive = [p.player_id for p in self.engine.runtime.public_state.players if p.alive]
        self.rng.shuffle(alive)
        return alive

    def _step_order(self) -> List[str]:
        alive = [p.player_id for p in self.engine.runtime.public_state.players if p.alive]
        return sorted(alive)

    def _ensure_step_order(self) -> None:
        runtime = self.engine.runtime
        if (
            runtime.turn_phase != runtime.public_state.phase
            or runtime.turn_round != runtime.public_state.round_num
            or not runtime.turn_order
        ):
            runtime.turn_phase = runtime.public_state.phase
            runtime.turn_round = runtime.public_state.round_num
            if runtime.public_state.phase == Phase.night:
                order: List[str] = []
                detective_id = runtime.detective_id
                if detective_id and runtime.get_player(detective_id) and runtime.get_player(detective_id).alive:
                    order.append(detective_id)
                murderer_id = runtime.murderer_id
                if murderer_id and runtime.get_player(murderer_id) and runtime.get_player(murderer_id).alive:
                    if murderer_id not in order:
                        order.append(murderer_id)
                runtime.turn_order = order
            else:
                runtime.turn_order = self._step_order()
            runtime.turn_index = 0
            runtime.cycle_passes.clear()

    def _apply_agent_action(self, player_id: str) -> ActionResponse | None:
        agent = self.agents.get(player_id)
        if agent is None:
            return None

        request = self._request_for(player_id)
        observation = self.engine.observation_for(player_id)
        agent.observe(observation)
        response = agent.act(request, observation)
        try:
            self.engine.apply_action(response)
            return response
        except ValueError:
            return None

    def _emit_public_message(self, body: str, *, actor_id: str = "narrator") -> GameEvent:
        event = GameEvent(
            event_id=f"evt_{uuid4().hex[:8]}",
            game_id=self.engine.runtime.public_state.game_id,
            ts_utc=datetime.now(timezone.utc).isoformat(),
            event_type=EventType.message_public,
            round_num=self.engine.runtime.public_state.round_num,
            phase=self.engine.runtime.public_state.phase,
            actor_id=actor_id,
            visibility=Visibility(mode="public", to=[]),
            payload={"body": body},
        )
        self.engine.runtime.event_history.append(event)
        self.engine._apply_event(event)
        return event

    def _opening_body_event(self) -> GameEvent:
        return self._emit_public_message(
            "A body is discovered at dawn. The town is shaken, but all players remain in the game."
        )

    def _emit_summary(self) -> None:
        if self.summary_agent is None:
            return
        runtime = self.engine.runtime
        start_idx = runtime.last_summary_index
        events = runtime.event_history[start_idx:]
        public_state_json = runtime.public_state.model_dump_json(indent=2)
        transcript_json = runtime.public_memory.model_dump_json(indent=2)
        events_json = (
            "[" + ", ".join(evt.model_dump_json() for evt in events) + "]"
            if events
            else "[]"
        )
        summary = self.summary_agent.summarize(public_state_json, transcript_json, events_json).strip()
        if summary:
            self._emit_public_message(summary, actor_id="narrator")
            runtime.last_summary_index = len(runtime.event_history)

    def _emit_pending_reveals(self) -> None:
        runtime = self.engine.runtime
        if not runtime.pending_reveals:
            return
        due = [item for item in runtime.pending_reveals if item.get("round_due") == runtime.public_state.round_num]
        if not due:
            return
        for item in due:
            target_id = item.get("target_player_id", "unknown")
            role = item.get("role", "unknown")
            self._emit_public_message(
                f"Investigation result (from two days ago): {target_id} is {role}.",
                actor_id="narrator",
            )
        runtime.pending_reveals = [item for item in runtime.pending_reveals if item.get("round_due") != runtime.public_state.round_num]

    def _update_memories(self) -> None:
        runtime = self.engine.runtime
        transcript_json = runtime.public_memory.model_dump_json(indent=2)
        for player_id, agent in self.agents.items():
            if not hasattr(agent, "client"):
                continue
            client = getattr(agent, "client", None)
            if client is None or not hasattr(client, "generate_memory_update"):
                continue
            player = runtime.get_player(player_id)
            if player is None or not player.alive:
                continue
            observation = self.engine.observation_for(player_id)
            observation_json = observation.model_dump_json(indent=2)
            update = client.generate_memory_update(observation_json, transcript_json)
            if not update:
                continue
            memory = runtime.private_memories.get(player_id)
            if memory is None:
                continue
            suspicion = update.get("suspicion_scores")
            if isinstance(suspicion, dict):
                cleaned = dict(memory.beliefs.suspicion)
                for key, val in suspicion.items():
                    try:
                        cleaned[str(key).lower()] = float(val)
                    except (TypeError, ValueError):
                        continue
                memory.beliefs.suspicion = cleaned
            if isinstance(update.get("top_suspects"), list):
                memory.beliefs.top_suspects = [str(x) for x in update.get("top_suspects", [])]
            if isinstance(update.get("trusted"), list):
                memory.beliefs.trusted = [str(x) for x in update.get("trusted", [])]
            if isinstance(update.get("plan_next"), str):
                memory.plan_next = update.get("plan_next", "")

    def _on_day_start(self) -> None:
        self._emit_pending_reveals()
        self._emit_summary()
        if self.engine.runtime.public_state.round_num > 1:
            self._update_memories()

    def step_phase(self) -> None:
        phase = self.engine.runtime.public_state.phase
        if phase == Phase.setup:
            self.engine.start()
            return

        if phase == Phase.night:
            if self.engine.runtime.public_state.round_num == 1:
                detective_id = self.engine.runtime.detective_id
                if detective_id and detective_id in self.agents:
                    self._apply_agent_action(detective_id)
                self._opening_body_event()
                self.engine.advance_phase()
                self._on_day_start()
                return
            detective_id = self.engine.runtime.detective_id
            if detective_id and detective_id in self.agents:
                self._apply_agent_action(detective_id)
            murderer = self.engine.runtime.murderer_id
            if murderer in self.agents:
                self._apply_agent_action(murderer)
            self.engine.advance_phase()
            self._on_day_start()
            return

        if phase == Phase.day:
            safety = 0
            while self.engine.runtime.public_state.phase == Phase.day:
                self.step_action()
                safety += 1
                if safety > 200:
                    break
            return

        if phase == Phase.vote:
            for player_id in self._turn_order():
                self._apply_agent_action(player_id)
            self.engine.resolve_votes()
            self._update_memories()
            self.engine.advance_phase()
            return

    def run_until_end(self, max_rounds: int = 10) -> None:
        if self.engine.runtime.public_state.phase == Phase.setup:
            self.engine.start()

        while self.engine.runtime.public_state.phase != Phase.ended:
            if self.engine.runtime.public_state.round_num > max_rounds:
                break
            self.step_phase()

    def run_round(self) -> None:
        if self.engine.runtime.public_state.phase == Phase.setup:
            self.engine.start()

        start_round = self.engine.runtime.public_state.round_num
        safety = 0
        while self.engine.runtime.public_state.phase != Phase.ended:
            if self.engine.runtime.public_state.round_num > start_round:
                break
            self.step_phase()
            safety += 1
            if safety > 12:
                break

    def step_action(self) -> List[GameEvent]:
        before = len(self.engine.runtime.event_history)
        phase = self.engine.runtime.public_state.phase
        if phase == Phase.setup:
            self.engine.start()
            return self.engine.runtime.event_history[before:]

        if phase == Phase.ended:
            return []

        if phase == Phase.night and self.engine.runtime.public_state.round_num == 1:
            runtime = self.engine.runtime
            detective_id = runtime.detective_id
            if detective_id and not runtime.night1_investigation_done and detective_id in self.agents:
                self._apply_agent_action(detective_id)
                runtime.night1_investigation_done = True
                return self.engine.runtime.event_history[before:]
            if not runtime.night1_body_emitted:
                self._opening_body_event()
                runtime.night1_body_emitted = True
                self.engine.advance_phase()
                self._on_day_start()
            return self.engine.runtime.event_history[before:]

        runtime = self.engine.runtime
        if phase == Phase.day and runtime.pending_question_to:
            target_id = runtime.pending_question_to
            target = runtime.get_player(target_id)
            if target is None or not target.alive:
                runtime.pending_question_from = None
                runtime.pending_question_to = None
                runtime.pending_question_body = None
                return self.engine.runtime.event_history[before:]
            runtime.free_reply_player_id = target_id
            self._apply_agent_action(target_id)
            runtime.free_reply_player_id = None
            runtime.pending_question_from = None
            runtime.pending_question_to = None
            runtime.pending_question_body = None
            all_out = all(p.social_ap <= 0 for p in runtime.public_state.players if p.alive)
            all_passed = False
            if all_out or all_passed:
                runtime.cycle_passes.clear()
                runtime.turn_order = []
                runtime.turn_index = 0
                self.engine.advance_phase()
            return self.engine.runtime.event_history[before:]

        self._ensure_step_order()
        if runtime.turn_index >= len(runtime.turn_order) and runtime.public_state.phase != Phase.ended:
            if phase == Phase.vote:
                self.engine.resolve_votes()
                self._update_memories()
            if phase in (Phase.night, Phase.vote):
                self.engine.advance_phase()
                if runtime.public_state.phase == Phase.day:
                    self._on_day_start()
            return self.engine.runtime.event_history[before:]

        player_id = runtime.turn_order[runtime.turn_index]
        runtime.turn_index += 1
        response = self._apply_agent_action(player_id)

        if phase == Phase.day:
            if response and response.action.action_type == ActionType.pass_turn:
                runtime.cycle_passes.add(player_id)
            elif response:
                runtime.cycle_passes.clear()

            alive_ids = [p.player_id for p in runtime.public_state.players if p.alive]
            all_out = all(p.social_ap <= 0 for p in runtime.public_state.players if p.alive)
            all_passed = set(alive_ids).issubset(runtime.cycle_passes)
            if runtime.pending_question_to:
                return self.engine.runtime.event_history[before:]
            if all_out or all_passed:
                runtime.cycle_passes.clear()
                runtime.turn_order = []
                runtime.turn_index = 0
                self.engine.advance_phase()
                return self.engine.runtime.event_history[before:]

        if runtime.turn_index >= len(runtime.turn_order):
            if phase == Phase.vote:
                self.engine.resolve_votes()
                self._update_memories()
            if phase in (Phase.night, Phase.vote):
                self.engine.advance_phase()
                if runtime.public_state.phase == Phase.day:
                    self._on_day_start()
            if phase == Phase.day:
                runtime.turn_index = 0
                runtime.cycle_passes.clear()

        return self.engine.runtime.event_history[before:]
