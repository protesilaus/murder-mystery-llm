# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Run Commands

```bash
# Install dependencies (use uv, pip, or poetry)
uv pip install -e ".[dev]"

# Run the server
uvicorn mmllm.web.main:app --host 127.0.0.1 --port 8000 --reload

# Run all tests
pytest

# Run a single test file
pytest tests/test_engine.py

# Run a specific test
pytest tests/test_engine.py::test_function_name -v

# Lint with ruff
ruff check src/

# Format with ruff
ruff format src/
```

## Architecture Overview

This is a Mafia-style social deduction game simulator with LLM agents. The core flow:

```
FastAPI Server → GameEngine (state) ↔ GameLoop (turn orchestration) → Agents → LLM Clients
```

### Key Design Patterns

1. **Event Sourcing**: All state changes emit `GameEvent` objects, persisted to JSONL in `runs/{game_id}/events.jsonl`. State can be rebuilt via `GameEngine.rebuild_from_events()`.

2. **Dual Memory System**: Public transcript (visible to all) + private per-player beliefs (suspicion scores, trusted players).

3. **Action Point Economy**: Players have `social_ap` budget per day phase. `speak`: 1 AP, `question`: 2 AP, `poll`: 2 AP.

4. **Configurable Game Types**: Rules defined in `GameTypeConfig` (loaded from `configs/gametypes/*.json`) - phases, roles, actions, win conditions.

5. **Action Validation Pipeline**: `LLM Response → parse_action() → Pydantic validation → adjudicator.apply_action() → GameEvent`

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `game/engine.py` | Game state management, phase transitions |
| `game/loop.py` | Turn orchestration, agent coordination |
| `game/rules.py` | Win conditions, action legality (config-driven) |
| `game/adjudicator.py` | Action validation, effect application |
| `core/game_config.py` | Game type configuration models |
| `data/gametype_config.py` | Load/save game type JSON files |
| `llm/local_client.py` | Ollama HTTP communication |
| `llm/prompt_builder.py` | Prompt template assembly |
| `llm/output_parser.py` | LLM response → typed action |

### Agent Abstraction

```python
class Agent(ABC):
    def observe(self, obs: AgentObservation) -> None: ...
    def act(self, req: ActionRequest) -> ActionResponse: ...
```

Implementations: `LLMAgent` (calls LLM), `ScriptedAgent` (random/testing), `SummaryAgent` (narration).

## Code Conventions

- Python 3.11+ with type hints on all function signatures
- Pydantic models for all data structures (immutable with `frozen=True` where appropriate)
- async/await for I/O operations
- `pathlib.Path` for file paths
- All state changes must emit events (event sourcing)

## Configuration

| File | Purpose |
|------|---------|
| `configs/app.yaml` | App settings (host, port, LLM provider) |
| `configs/game_rules.yaml` | Game parameters |
| `configs/prompts.yaml` | LLM prompt templates |
| `configs/party.json` | Player roster |
| `configs/gametypes/*.json` | Game type definitions |
| `.env` | API keys (see `.env.example`) |
