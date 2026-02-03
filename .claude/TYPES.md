# Key Types and Data Models

All models are Pydantic classes in `src/mmllm/core/types.py`.

## Enums

### Role
```python
class Role(str, Enum):
    town = "town"           # Regular townsperson
    murderer = "murderer"   # The killer
    detective = "detective" # Can investigate at night
```

### Phase
```python
class Phase(str, Enum):
    setup = "setup"   # Game initialization
    night = "night"   # Murderer kills, detective investigates
    day = "day"       # Public discussion
    vote = "vote"     # Players vote to eliminate
    ended = "ended"   # Game finished
```

### ActionType
```python
class ActionType(str, Enum):
    speak = "speak"
    vote = "vote"
    kill = "kill"
    investigate = "investigate"
    question = "question"
    poll = "poll"
    whisper_send = "whisper_send"
    whisper_reply = "whisper_reply"
    pass_turn = "pass"
```

## Game State Models

### PublicState
```python
class PublicState(BaseModel):
    game_id: str
    round_num: int
    phase: Phase
    players: List[PlayerState]
    current_votes: Dict[str, str]  # voter_id → target_id
    last_night_kill: Optional[str]
    last_day_eliminated: Optional[str]
```

### PlayerState
```python
class PlayerState(BaseModel):
    player_id: str
    alive: bool
    social_ap: int  # Action points for day phase
    controls: PlayerControls  # available actions
```

### PrivateMemory
```python
class PrivateMemory(BaseModel):
    player_id: str
    round_num: int
    beliefs: PrivateBeliefs
    claims_to_follow_up: List[str]
    contradictions: List[str]
    private_messages: List[TranscriptEntry]
```

### PrivateBeliefs
```python
class PrivateBeliefs(BaseModel):
    suspicion: Dict[str, float]  # player_id → 0.0-1.0
    top_suspects: List[str]
    trusted: List[str]
```

## Agent Communication

### AgentObservation
What the agent sees before acting:
```python
class AgentObservation(BaseModel):
    public_state: PublicState
    public_memory: PublicMemory
    private_memory: Optional[PrivateMemory]
    role: Role
    legal_actions: List[ActionType]
```

### ActionRequest
What action is needed:
```python
class ActionRequest(BaseModel):
    game_id: str
    player_id: str
    phase: Phase
    round_num: int
    action_hint: Optional[str]
```

### ActionResponse (Discriminated Union)
```python
ActionResponse = Union[
    SpeakAction,
    VoteAction,
    KillAction,
    InvestigateAction,
    QuestionAction,
    PollAction,
    WhisperSendAction,
    WhisperReplyAction,
    PassAction,
]
```

### Example Actions
```python
class SpeakAction(BaseModel):
    action_type: Literal["speak"]
    body: str

class VoteAction(BaseModel):
    action_type: Literal["vote"]
    target: str  # player_id to vote for

class KillAction(BaseModel):
    action_type: Literal["kill"]
    target: str  # player_id to kill
```

## Event System

### GameEvent
```python
class GameEvent(BaseModel):
    event_id: str
    game_id: str
    ts_utc: datetime
    event_type: str
    round_num: int
    phase: Phase
    actor_id: Optional[str]
    payload: Dict[str, Any]
```

### Event Types
- `game_created`, `phase_started`, `game_ended`
- `message_public`, `message_private`
- `vote_cast`, `vote_resolved`
- `night_kill`, `player_eliminated`
- `round_summary`, `memory_updated`

## Runtime State

### GameRuntime
```python
class GameRuntime:
    game_id: str
    public_state: PublicState
    public_memory: PublicMemory
    private_memories: Dict[str, PrivateMemory]
    roles: Dict[str, Role]
    event_history: List[GameEvent]
    turn_order: List[str]
    turn_index: int
```
