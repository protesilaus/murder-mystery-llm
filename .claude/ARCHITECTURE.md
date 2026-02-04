# Architecture

## Component Flow
```
┌─────────────────────────────────────────────────────────┐
│              FastAPI Web Server (port 8000)             │
└─────────────┬───────────────────────────────────────────┘
              │
    ┌─────────┴─────────────────────────┐
    │                                   │
    ▼                                   ▼
┌──────────────────┐       ┌───────────────────────┐
│  API Routes      │       │  Web UI (Jinja2)      │
│  /games, /agents │       │  /, /game/{id}, /test │
│  /party, /runs   │       └───────────────────────┘
└────────┬─────────┘
         │
    ┌────┴────────────────────────────────┐
    │                                     │
    ▼                                     ▼
┌─────────────────┐              ┌──────────────────┐
│  GameEngine     │◄────────────►│  GameLoop        │
│  - State mgmt   │              │  - Turn order    │
│  - Phase trans  │              │  - Agent calls   │
│  - Action valid │              │  - Event emit    │
└────────┬────────┘              └──────────────────┘
         │
    ┌────┴───────────────────────────────┐
    │                                    │
    ▼                                    ▼
┌──────────────────────┐    ┌────────────────────┐
│  GameRuntime State   │    │  Agents            │
│  - public_state      │    │  - LLMAgent        │
│  - private_memories  │    │  - ScriptedAgent   │
│  - event_history     │    │  - SummaryAgent    │
└──────────────────────┘    └─────────┬──────────┘
                                      │
                                      ▼
                           ┌────────────────────────┐
                           │  LLM Clients           │
                           │  - LocalClient(Ollama) │
                           │  - OpenAIClient        │
                           └────────────────────────┘
```

## Game Flow
```
Night Phase          Day Phase           Vote Phase
    │                    │                   │
    ▼                    ▼                   ▼
Detective         All players speak    All players vote
investigates      (costs AP)           (1 vote each)
    │                    │                   │
    ▼                    │                   ▼
Murderer          Questions, polls     Tally votes
kills victim      Whispers             Eliminate player
    │                    │                   │
    └────────────────────┴───────────────────┘
                         │
                         ▼
              Check win condition
              (Murderer dead = Town wins)
              (Town ≤ 1 = Murderer wins)
```

## Key Patterns

### 1. Event Sourcing
- All game state changes emit `GameEvent` objects
- Events written to JSONL: `runs/{game_id}/events.jsonl`
- State can be rebuilt via `GameEngine.rebuild_from_events()`

### 2. Agent Abstraction
```python
class Agent(ABC):
    def observe(self, obs: AgentObservation) -> None: ...
    def act(self, req: ActionRequest) -> ActionResponse: ...
```
- `LLMAgent`: Calls LLM client for decisions
- `ScriptedAgent`: Random actions (testing)
- `SummaryAgent`: Generates round narration

### 3. Dual Memory System
- **Public Memory**: Transcript visible to all players
- **Private Memory**: Per-player beliefs (suspicion scores, trusted players)

### 4. Action Validation Pipeline
```
LLM Response → parse_action() → Pydantic validation → adjudicator.apply_action() → GameEvent
```

### 5. Action Point Economy
- Players have `social_ap` budget per day phase
- `speak`: 1 AP, `question`: 2 AP, `poll`: 2 AP
- Forces strategic communication choices

### 6. Configurable Game Types
Game rules are defined in `GameTypeConfig` (loaded from JSON files in `configs/gametypes/`):
```python
GameTypeConfig:
  - phases: List[PhaseConfig]      # Phase order, turn order, end conditions
  - roles: Dict[str, RoleConfig]   # Team, abilities per role
  - actions: Dict[str, ActionConfig]  # AP costs, thresholds, phases
  - win_conditions: List[WinCondition]  # How each team wins
  - special_rules: SpecialRules    # Round 1 behavior, delays
```

Turn order per phase is configurable:
- `sequential`: Sorted by player_id
- `role_priority`: Specific roles act first (e.g., detective, then murderer)
- `random`: Shuffled order

### 7. Real-Time Execution Status (NEW)
The game loop now tracks and exposes its execution state for real-time UI updates:

```python
class ExecutionStatus(Enum):
    idle = "idle"
    querying_llm = "querying_llm"
    waiting_response = "waiting_response"
    applying_action = "applying_action"
    phase_transition = "phase_transition"

class GameStatus:
    status: ExecutionStatus
    current_actor: str | None
    action_description: str  # Human-readable status
    request_id: str | None   # Link to stored LLM prompt
    timestamp: str
```

**Status Update Points** (in `loop.py:_apply_agent_action()`):
1. Before requesting action → `querying_llm`
2. Before LLM call → `waiting_response`
3. Before applying action → `applying_action`
4. After completion → `idle`

**Frontend Polling**:
- UI polls `GET /{game_id}/status` every 500ms
- Displays status with icons (💭 querying, ⏳ waiting, ⚙️ applying, ⏸️ idle)
- Shows "View Query Sent" link to inspect LLM prompts

**Prompt Storage**:
- LLM prompts captured in `local_client.py` via callback
- Stored in memory: `_PROMPT_STORE[game_id][request_id]`
- Retrieved via `GET /{game_id}/prompts/{request_id}`
- Includes: messages, timestamp, player info, LLM response

## Module Responsibilities

| Module | Single Responsibility |
|--------|----------------------|
| `game_config.py` | Game type configuration models |
| `gametype_config.py` | Load/save game type JSON files |
| `engine.py` | Game state management and phase transitions |
| `loop.py` | Turn orchestration, agent coordination, execution status tracking |
| `rules.py` | Win conditions and action legality (config-driven) |
| `adjudicator.py` | Action validation and effect application (config-driven) |
| `local_client.py` | Ollama HTTP communication, prompt capture |
| `prompt_builder.py` | Prompt template assembly |
| `output_parser.py` | LLM response → typed action |
| `event_log.py` | JSONL persistence |
| `routes_games.py` | Game API endpoints, status polling, prompt retrieval |
| `status.js` | Frontend status polling and display |
