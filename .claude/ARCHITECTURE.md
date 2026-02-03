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

## Module Responsibilities

| Module | Single Responsibility |
|--------|----------------------|
| `engine.py` | Game state management and phase transitions |
| `loop.py` | Turn orchestration and agent coordination |
| `rules.py` | Win conditions and action legality |
| `adjudicator.py` | Action validation and effect application |
| `local_client.py` | Ollama HTTP communication |
| `prompt_builder.py` | Prompt template assembly |
| `output_parser.py` | LLM response → typed action |
| `event_log.py` | JSONL persistence |
