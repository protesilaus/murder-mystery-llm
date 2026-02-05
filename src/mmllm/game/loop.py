"""Gameplay loop orchestration."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

logger = logging.getLogger(__name__)

from mmllm.agents.base import Agent
from mmllm.agents.llm_agent import LLMAgent
from mmllm.agents.summary_agent import SummaryAgent
from mmllm.core.game_config import GameTypeConfig, TurnOrder
from mmllm.core.rng import RNG
from mmllm.core.types import (
    ActionRequest,
    ActionResponse,
    ActionType,
    EventType,
    ExecutionStatus,
    GameEvent,
    GameStatus,
    Phase,
    Visibility,
)
from mmllm.game.engine import GameEngine
from mmllm.game.rules import legal_actions


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
        alive = [
            p.player_id for p in self.engine.runtime.public_state.players if p.alive
        ]
        self.rng.shuffle(alive)
        return alive

    def _step_order(self) -> List[str]:
        alive = [
            p.player_id for p in self.engine.runtime.public_state.players if p.alive
        ]
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

            # Get phase config for turn order
            config = runtime.game_config or GameTypeConfig.default_classic()
            phase_config = config.get_phase_config(runtime.public_state.phase.value)

            if phase_config and phase_config.turn_order == TurnOrder.role_priority:
                # Use role priority order from config
                order: List[str] = []
                for role_name in phase_config.role_priority:
                    for pid, role in runtime.roles.items():
                        if role.value == role_name:
                            player = runtime.get_player(pid)
                            if player and player.alive and pid not in order:
                                order.append(pid)
                runtime.turn_order = order
            elif phase_config and phase_config.turn_order == TurnOrder.random:
                # Use random shuffle
                runtime.turn_order = self._turn_order()
            else:
                # Default: sequential (sorted) order
                runtime.turn_order = self._step_order()

            runtime.turn_index = 0
            runtime.cycle_passes.clear()

    def _apply_agent_action(self, player_id: str) -> ActionResponse | None:
        runtime = self.engine.runtime

        # Update: Requesting action
        runtime.execution_status = GameStatus(
            status=ExecutionStatus.querying_llm,
            current_actor=player_id,
            action_description=f"Requesting action from {player_id}",
        )

        agent = self.agents.get(player_id)
        if agent is None:
            runtime.execution_status = GameStatus(status=ExecutionStatus.idle)
            return None

        request = self._request_for(player_id)
        runtime.execution_status.request_id = request.request_id

        # Update: Waiting for LLM response
        runtime.execution_status.status = ExecutionStatus.waiting_response
        runtime.execution_status.action_description = (
            f"Waiting for {player_id} response"
        )

        observation = self.engine.observation_for(player_id)
        agent.observe(observation)
        response = agent.act(request, observation)

        # Update: Applying action
        runtime.execution_status.status = ExecutionStatus.applying_action
        runtime.execution_status.action_description = f"Applying {player_id}'s action"

        # DEBUG: Log the action being attempted
        logger.info(
            "Applying action: player=%s action_type=%s",
            player_id,
            response.action.type.value,
        )

        try:
            events = self.engine.apply_action(response)
            logger.info(
                "Action applied successfully: player=%s action_type=%s events_created=%d",
                player_id,
                response.action.type.value,
                len(events),
            )
            return response
        except ValueError as exc:
            logger.warning(
                "Action failed with ValueError: player=%s action_type=%s error=%s",
                player_id,
                response.action.type.value,
                str(exc),
            )
            return None
        except Exception as exc:
            logger.exception(
                "Action failed with unexpected exception: player=%s action_type=%s",
                player_id,
                response.action.type.value,
            )
            return None
        finally:
            # Reset to idle
            runtime.execution_status = GameStatus(status=ExecutionStatus.idle)

    def _emit_public_message(
        self, body: str, *, actor_id: str = "narrator"
    ) -> GameEvent:
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

        # Filter to only public events - don't leak private messages to the summary
        public_events = [evt for evt in events if evt.visibility.mode == "public"]

        public_state_json = runtime.public_state.model_dump_json(indent=2)
        transcript_json = runtime.public_memory.model_dump_json(indent=2)
        events_json = json.dumps([evt.model_dump() for evt in public_events], indent=2)
        summary = self.summary_agent.summarize(
            public_state_json, transcript_json, events_json
        ).strip()
        if summary:
            self._emit_public_message(summary, actor_id="narrator")
            runtime.last_summary_index = len(runtime.event_history)

    def _emit_pending_reveals(self) -> None:
        runtime = self.engine.runtime
        if not runtime.pending_reveals:
            return
        due = [
            item
            for item in runtime.pending_reveals
            if item.get("round_due") == runtime.public_state.round_num
        ]
        if not due:
            return
        for item in due:
            target_id = item.get("target_player_id", "unknown")
            role = item.get("role", "unknown")
            self._emit_public_message(
                f"Investigation result (from two days ago): {target_id} is {role}.",
                actor_id="narrator",
            )
        runtime.pending_reveals = [
            item
            for item in runtime.pending_reveals
            if item.get("round_due") != runtime.public_state.round_num
        ]

    def _update_memories(self) -> None:
        runtime = self.engine.runtime
        transcript_json = runtime.public_memory.model_dump_json(indent=2)
        for player_id, agent in self.agents.items():
            # Only LLMAgents support memory updates
            if not isinstance(agent, LLMAgent):
                continue
            client = agent.client
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
                memory.beliefs.top_suspects = [
                    str(x) for x in update.get("top_suspects", [])
                ]
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
        config = self.engine.runtime.game_config or GameTypeConfig.default_classic()

        if phase == Phase.setup:
            self.engine.start()
            return

        if phase == Phase.night:
            is_round_1 = self.engine.runtime.public_state.round_num == 1
            skip_kill_round_1 = config.special_rules.round_1_skip_kill

            if is_round_1 and skip_kill_round_1:
                # Round 1 special case: only detective acts, then body event
                detective_id = self.engine.runtime.detective_id
                if detective_id and detective_id in self.agents:
                    self._apply_agent_action(detective_id)
                if config.special_rules.opening_body_event:
                    self._opening_body_event()
                self.engine.advance_phase()
                self._on_day_start()
                return

            # Normal night: use turn order from config
            self._ensure_step_order()
            for player_id in self.engine.runtime.turn_order:
                if player_id in self.agents:
                    self._apply_agent_action(player_id)
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

        if phase == Phase.analysis:
            # Analysis phase: players review others and update suspicion
            self._ensure_step_order()
            for player_id in self.engine.runtime.turn_order:
                if player_id in self.agents:
                    self._apply_agent_action(player_id)
            self._update_memories()
            self.engine.advance_phase()
            return

        if phase == Phase.vote:
            self._ensure_step_order()
            for player_id in self.engine.runtime.turn_order:
                if player_id in self.agents:
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
        config = self.engine.runtime.game_config or GameTypeConfig.default_classic()

        if phase == Phase.setup:
            self.engine.start()
            return self.engine.runtime.event_history[before:]

        if phase == Phase.ended:
            return []

        # Handle round 1 night special case (if configured)
        is_round_1 = self.engine.runtime.public_state.round_num == 1
        skip_kill_round_1 = config.special_rules.round_1_skip_kill

        if phase == Phase.night and is_round_1 and skip_kill_round_1:
            runtime = self.engine.runtime
            detective_id = runtime.detective_id
            if (
                detective_id
                and not runtime.night1_investigation_done
                and detective_id in self.agents
            ):
                self._apply_agent_action(detective_id)
                runtime.night1_investigation_done = True
                return self.engine.runtime.event_history[before:]
            if not runtime.night1_body_emitted:
                if config.special_rules.opening_body_event:
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
            all_out = all(
                p.social_ap <= 0 for p in runtime.public_state.players if p.alive
            )
            all_passed = False
            if all_out or all_passed:
                runtime.cycle_passes.clear()
                runtime.turn_order = []
                runtime.turn_index = 0
                self.engine.advance_phase()
            return self.engine.runtime.event_history[before:]

        self._ensure_step_order()
        if (
            runtime.turn_index >= len(runtime.turn_order)
            and runtime.public_state.phase != Phase.ended
        ):
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
            if response and response.action.type == ActionType.pass_turn:
                runtime.cycle_passes.add(player_id)
            elif response:
                runtime.cycle_passes.clear()

            alive_ids = [p.player_id for p in runtime.public_state.players if p.alive]
            all_out = all(
                p.social_ap <= 0 for p in runtime.public_state.players if p.alive
            )
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

    def preview_next_actor(self) -> dict:
        """Preview who will act next without executing the action."""
        runtime = self.engine.runtime
        phase = runtime.public_state.phase
        config = runtime.game_config or GameTypeConfig.default_classic()

        # Check for pending question response
        if phase == Phase.day and runtime.pending_question_to:
            target_id = runtime.pending_question_to
            target = runtime.get_player(target_id)
            if target and target.alive:
                return {
                    "actor_id": target_id,
                    "actor_type": "player",
                    "reason": "responding_to_question",
                }

        # Check for round 1 night special cases
        is_round_1 = runtime.public_state.round_num == 1
        skip_kill_round_1 = config.special_rules.round_1_skip_kill

        if phase == Phase.night and is_round_1 and skip_kill_round_1:
            detective_id = runtime.detective_id
            if detective_id and not runtime.night1_investigation_done:
                return {
                    "actor_id": detective_id,
                    "actor_type": "player",
                    "reason": "night1_investigation",
                }
            if (
                not runtime.night1_body_emitted
                and config.special_rules.opening_body_event
            ):
                return {
                    "actor_id": "narrator",
                    "actor_type": "narrator",
                    "reason": "opening_body_event",
                }

        # Ensure turn order is set up
        self._ensure_step_order()

        # Check if we're at the end of turn order
        if runtime.turn_index >= len(runtime.turn_order):
            if phase == Phase.vote:
                return {
                    "actor_id": "narrator",
                    "actor_type": "narrator",
                    "reason": "resolve_votes",
                }
            if phase in (Phase.night, Phase.vote):
                return {
                    "actor_id": "narrator",
                    "actor_type": "narrator",
                    "reason": "phase_advance",
                }
            if phase == Phase.day:
                # Day phase loops, so reset to start
                if runtime.turn_order:
                    return {
                        "actor_id": runtime.turn_order[0],
                        "actor_type": "player",
                        "reason": "new_cycle",
                    }

        # Get the next player in turn order
        if runtime.turn_index < len(runtime.turn_order):
            player_id = runtime.turn_order[runtime.turn_index]
            return {
                "actor_id": player_id,
                "actor_type": "player",
                "reason": "normal_turn",
            }

        # Fallback - phase transition
        return {
            "actor_id": "narrator",
            "actor_type": "narrator",
            "reason": "phase_transition",
        }
