"""Dataclasses and models for events, actions, and game state."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ----------------------------
# Enums
# ----------------------------


class Role(str, Enum):
    town = "town"
    murderer = "murderer"
    detective = "detective"


class Phase(str, Enum):
    setup = "setup"
    night = "night"
    day = "day"
    vote = "vote"
    ended = "ended"


class ActionType(str, Enum):
    speak = "speak"
    question = "question"
    poll = "poll"
    investigate = "investigate"
    whisper_send = "whisper_send"
    whisper_reply = "whisper_reply"
    vote = "vote"
    kill = "kill"
    pass_turn = "pass"


class EventType(str, Enum):
    game_created = "game_created"
    phase_started = "phase_started"
    message_public = "message_public"
    message_private = "message_private"
    vote_cast = "vote_cast"
    vote_resolved = "vote_resolved"
    night_kill = "night_kill"
    player_eliminated = "player_eliminated"
    round_summary = "round_summary"
    memory_updated = "memory_updated"
    game_ended = "game_ended"


# ----------------------------
# ID helpers
# ----------------------------


def _is_lowerish(s: str) -> bool:
    # Accepts digits, underscores, and lowercase ascii letters; common for ids like "p1", "game_..."
    return s == s.lower()


class IdModel(BaseModel):
    """Base model with strict config and lower-case ID validation helpers."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    @staticmethod
    def _lower_id(v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("id must be a non-empty string")
        v = v.strip()
        if not _is_lowerish(v):
            raise ValueError("id must be lower case")
        return v


# ----------------------------
# Control knobs (numeric) + derived constraints
# ----------------------------


class Controls(IdModel):
    # All 0..1 numeric knobs; keep them general and evolve/mutate freely.
    assertiveness: float = Field(0.5, ge=0.0, le=1.0)
    skepticism: float = Field(0.5, ge=0.0, le=1.0)
    query_rate: float = Field(0.5, ge=0.0, le=1.0)
    risk: float = Field(0.5, ge=0.0, le=1.0)
    deception: float = Field(0.0, ge=0.0, le=1.0)
    verbosity: float = Field(0.5, ge=0.0, le=1.0)


class Constraints(IdModel):
    # These are *engine-enforced* turn constraints derived from Controls + seeded RNG.
    max_sentences: int = Field(2, ge=1, le=5)
    must_ask_question: bool = False
    must_cite_evidence: bool = False
    hedge_budget: int = Field(1, ge=0, le=5)
    follow_plurality_bias: float = Field(0.5, ge=0.0, le=1.0)
    # Optional: cap for message length enforcement
    max_chars: int = Field(280, ge=50, le=2000)


# ----------------------------
# Core game state models
# ----------------------------


class PlayerState(IdModel):
    player_id: str
    alive: bool = True

    # Social action points (AP) per round/day
    social_ap_max: int = Field(3, ge=0, le=20)
    social_ap: int = Field(3, ge=0, le=20)

    # Optional: numeric knobs (genome) for this player
    controls: Controls = Field(default_factory=Controls)

    @field_validator("player_id")
    @classmethod
    def _v_player_id(cls, v: str) -> str:
        return cls._lower_id(v)


class PublicState(IdModel):
    game_id: str
    round_num: int = Field(1, ge=1)
    phase: Phase = Phase.setup

    players: List[PlayerState]

    # Canonical facts (engine-owned)
    last_night_kill: Optional[str] = None  # player_id
    last_day_eliminated: Optional[str] = None  # player_id

    # Voting snapshot for current vote phase
    current_votes: Dict[str, str] = Field(default_factory=dict)  # voter_id -> target_id

    @field_validator("game_id")
    @classmethod
    def _v_game_id(cls, v: str) -> str:
        return cls._lower_id(v)

    @field_validator("last_night_kill", "last_day_eliminated")
    @classmethod
    def _v_optional_pid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return cls._lower_id(v)

    @field_validator("current_votes")
    @classmethod
    def _v_votes(cls, v: Dict[str, str]) -> Dict[str, str]:
        return {cls._lower_id(k): cls._lower_id(val) for k, val in v.items()}


class Visibility(IdModel):
    """
    Who can see an event/message.
    - public: everyone alive
    - direct: sender + receiver(s)
    - group: defined set (e.g., mafia team)
    """

    mode: Literal["public", "direct", "group"] = "public"
    to: List[str] = Field(default_factory=list)  # player_ids (for direct/group)

    @field_validator("to")
    @classmethod
    def _v_to(cls, v: List[str]) -> List[str]:
        return [cls._lower_id(x) for x in v]


class TranscriptEntry(IdModel):
    entry_id: str
    round_num: int = Field(1, ge=1)
    phase: Phase
    speaker_id: str
    body: str
    visibility: Visibility = Field(default_factory=Visibility)

    @field_validator("entry_id", "speaker_id")
    @classmethod
    def _v_ids(cls, v: str) -> str:
        return cls._lower_id(v)


class PublicMemory(IdModel):
    # Rolling summaries + transcript (public entries only)
    transcript: List[TranscriptEntry] = Field(default_factory=list)

    # Optional: short factual digest per round (engine-generated)
    event_digests: Dict[int, List[str]] = Field(default_factory=dict)  # round -> bullet facts

    # Optional: compressed summaries (LLM-generated, but treated as "notes", not facts)
    round_summaries: Dict[int, List[str]] = Field(default_factory=dict)  # round -> bullets


class PrivateBeliefs(IdModel):
    suspicion: Dict[str, float] = Field(default_factory=dict)  # player_id -> 0..1
    top_suspects: List[str] = Field(default_factory=list)
    trusted: List[str] = Field(default_factory=list)

    @field_validator("suspicion")
    @classmethod
    def _v_suspicion(cls, v: Dict[str, float]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for k, val in v.items():
            k2 = cls._lower_id(k)
            if not (0.0 <= float(val) <= 1.0):
                raise ValueError("suspicion values must be in [0,1]")
            out[k2] = float(val)
        return out

    @field_validator("top_suspects", "trusted")
    @classmethod
    def _v_pid_lists(cls, v: List[str]) -> List[str]:
        return [cls._lower_id(x) for x in v]


class PrivateMemory(IdModel):
    player_id: str
    round_num: int = Field(1, ge=1)

    beliefs: PrivateBeliefs = Field(default_factory=PrivateBeliefs)

    # Track things to follow up
    claims_to_follow_up: List[Dict[str, Any]] = Field(default_factory=list)
    contradictions: List[Dict[str, Any]] = Field(default_factory=list)
    plan_next: str = ""

    # Optional DM inbox/outbox (if you enable whispers)
    private_messages: List[TranscriptEntry] = Field(default_factory=list)

    @field_validator("player_id")
    @classmethod
    def _v_player_id(cls, v: str) -> str:
        return cls._lower_id(v)


class AgentObservation(IdModel):
    """
    What the agent sees at a decision point.
    Keep this stable so logs become training data.
    """

    game_id: str
    player_id: str
    round_num: int
    phase: Phase

    public_state: PublicState
    public_memory: PublicMemory

    # The agent's private role and private memory
    role: Role
    private_memory: PrivateMemory

    # Numeric controls + derived constraints for *this action opportunity*
    controls: Controls = Field(default_factory=Controls)
    constraints: Constraints = Field(default_factory=Constraints)

    @field_validator("game_id", "player_id")
    @classmethod
    def _v_ids(cls, v: str) -> str:
        return cls._lower_id(v)


# ----------------------------
# Action request/response schemas
# ----------------------------


class ActionRequest(IdModel):
    request_id: str
    game_id: str
    player_id: str
    round_num: int
    phase: Phase
    allowed_actions: List[ActionType]
    ap_available: int = Field(0, ge=0, le=20)
    constraints: Constraints = Field(default_factory=Constraints)

    @field_validator("request_id", "game_id", "player_id")
    @classmethod
    def _v_ids(cls, v: str) -> str:
        return cls._lower_id(v)


class ActionBase(IdModel):
    action_type: ActionType
    reasoning_private: Optional[str] = Field(
        default=None,
        description="Never shown publicly; stored for analysis/training.",
    )


class SpeakAction(ActionBase):
    action_type: Literal[ActionType.speak] = ActionType.speak
    body: str


class QuestionAction(ActionBase):
    action_type: Literal[ActionType.question] = ActionType.question
    to_player_id: str
    body: str

    @field_validator("to_player_id")
    @classmethod
    def _v_to(cls, v: str) -> str:
        return cls._lower_id(v)


class PollAction(ActionBase):
    action_type: Literal[ActionType.poll] = ActionType.poll
    body: str


class InvestigateAction(ActionBase):
    action_type: Literal[ActionType.investigate] = ActionType.investigate
    target_player_id: str

    @field_validator("target_player_id")
    @classmethod
    def _v_target(cls, v: str) -> str:
        return cls._lower_id(v)


class WhisperSendAction(ActionBase):
    action_type: Literal[ActionType.whisper_send] = ActionType.whisper_send
    to_player_id: str
    body: str

    @field_validator("to_player_id")
    @classmethod
    def _v_to(cls, v: str) -> str:
        return cls._lower_id(v)


class WhisperReplyAction(ActionBase):
    action_type: Literal[ActionType.whisper_reply] = ActionType.whisper_reply
    to_player_id: str
    body: str

    @field_validator("to_player_id")
    @classmethod
    def _v_to(cls, v: str) -> str:
        return cls._lower_id(v)


class VoteAction(ActionBase):
    action_type: Literal[ActionType.vote] = ActionType.vote
    target_player_id: str

    @field_validator("target_player_id")
    @classmethod
    def _v_target(cls, v: str) -> str:
        return cls._lower_id(v)


class KillAction(ActionBase):
    action_type: Literal[ActionType.kill] = ActionType.kill
    target_player_id: str

    @field_validator("target_player_id")
    @classmethod
    def _v_target(cls, v: str) -> str:
        return cls._lower_id(v)


class PassAction(ActionBase):
    action_type: Literal[ActionType.pass_turn] = ActionType.pass_turn
    note: Optional[str] = None


AgentAction = Union[
    SpeakAction,
    QuestionAction,
    PollAction,
    InvestigateAction,
    WhisperSendAction,
    WhisperReplyAction,
    VoteAction,
    KillAction,
    PassAction,
]


class ActionResponse(IdModel):
    request_id: str
    game_id: str
    player_id: str
    round_num: int
    phase: Phase

    action: AgentAction

    # Optional structured "beliefs" emitted alongside actions (useful for training)
    suspicion_scores: Optional[Dict[str, float]] = None

    @field_validator("request_id", "game_id", "player_id")
    @classmethod
    def _v_ids(cls, v: str) -> str:
        return cls._lower_id(v)

    @field_validator("suspicion_scores")
    @classmethod
    def _v_suspicion_scores(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if v is None:
            return None
        out: Dict[str, float] = {}
        for k, val in v.items():
            k2 = cls._lower_id(k)
            if not (0.0 <= float(val) <= 1.0):
                raise ValueError("suspicion_scores values must be in [0,1]")
            out[k2] = float(val)
        return out


# ----------------------------
# Event log schema (JSONL)
# ----------------------------


class ApDelta(IdModel):
    ap_before: int = Field(..., ge=0, le=20)
    ap_cost: int = Field(..., ge=0, le=20)
    ap_after: int = Field(..., ge=0, le=20)


class GameEvent(IdModel):
    """
    Single append-only event record for JSONL logs.
    Use `payload` for type-specific details; keep the outer envelope stable.
    """

    event_id: str
    game_id: str
    ts_utc: str  # ISO8601 timestamp string (engine sets this)

    event_type: EventType
    round_num: int = Field(1, ge=1)
    phase: Phase

    actor_id: Optional[str] = None  # player who caused it (if any)
    visibility: Visibility = Field(default_factory=Visibility)

    ap: Optional[ApDelta] = None

    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "game_id", "actor_id")
    @classmethod
    def _v_ids(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return cls._lower_id(v)


class GameResult(IdModel):
    game_id: str
    winner: Literal["town", "murderer"]
    rounds_played: int = Field(..., ge=1)
    eliminated_order: List[str] = Field(default_factory=list)  # player_ids
    murderer_id: str

    @field_validator("game_id", "murderer_id")
    @classmethod
    def _v_ids(cls, v: str) -> str:
        return cls._lower_id(v)

    @field_validator("eliminated_order")
    @classmethod
    def _v_elims(cls, v: List[str]) -> List[str]:
        return [cls._lower_id(x) for x in v]


class GameState(PublicState):
    """Backward-compatible alias for PublicState."""
