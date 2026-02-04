# Murder Mystery LLM - Project Overview

## What It Does
A Mafia-style social deduction game simulator powered by LLM agents. Players (AI agents) take on roles (Town, Murderer, Detective) and interact through discussion, investigation, and voting to find the killer.

**NEW: Real-Time Execution Status** - The UI now displays what's happening during game execution with live status updates (e.g., "Waiting for P1 response") and allows viewing the exact LLM prompts sent to each agent.

## Tech Stack
- **Python 3.11+** with modern async patterns
- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **Pydantic 2.6+** - Data validation and type safety
- **Jinja2** - Server-side HTML templates
- **PyYAML** - Configuration files
- **pytest** - Testing

## LLM Backends Supported
- **Ollama** (local) - Primary development target
- **OpenAI API** - Cloud option
- **LM Studio** - Alternative local inference

## Project Structure
```
murder-mystery-llm/
├── src/mmllm/           # Main source package
│   ├── agents/          # Agent implementations (LLM, Scripted, Summary)
│   ├── core/            # Types, clock, RNG, IDs
│   ├── data/            # Event logs, party config, storage
│   ├── game/            # Engine, loop, rules, adjudicator
│   ├── llm/             # LLM clients, prompts, parsing
│   ├── training/        # Dataset building, evaluation
│   └── web/             # FastAPI app, routes, templates
├── configs/             # YAML/JSON configuration
├── tests/               # pytest unit tests
├── scripts/             # Utility scripts
├── notebooks/           # Jupyter notebooks (server control)
├── runs/                # Game run artifacts (JSONL logs)
├── logs/                # Application logs
└── docker/              # Deployment assets
```

## Key Entry Points
- **Web Server**: `src/mmllm/web/main.py` → FastAPI app
- **Game Engine**: `src/mmllm/game/engine.py` → `GameEngine` class
- **Game Loop**: `src/mmllm/game/loop.py` → `GameLoop` class
- **Game Config**: `src/mmllm/core/game_config.py` → `GameTypeConfig` class
- **LLM Client**: `src/mmllm/llm/local_client.py` → `LocalClient` (Ollama)

## Running the Server
```bash
# From repo root with venv activated
uvicorn mmllm.web.main:app --host 127.0.0.1 --port 8000
```
Or use `notebooks/server_control.ipynb` for Jupyter-based control.

## Configuration Files
| File | Purpose |
|------|---------|
| `configs/app.yaml` | App settings (host, port, LLM provider) |
| `configs/game_rules.yaml` | Game parameters (player counts, phases) |
| `configs/prompts.yaml` | LLM prompt templates |
| `configs/party.json` | Current player roster |
| `configs/gametypes/*.json` | Game type definitions (phases, roles, actions, win conditions) |
| `.env` | API keys and URLs |

## Game Types
Game types are defined as JSON files in `configs/gametypes/`. Each defines:
- **Phases**: Order, turn order type, end conditions
- **Roles**: Teams, abilities, counts
- **Actions**: AP costs, thresholds, available phases
- **Win Conditions**: How each team wins
- **Special Rules**: Round 1 behavior, investigation delays

Built-in types:
- `classic` - Default murder mystery with detective (always available)
- `quick` - Faster variant with more AP and immediate investigation results

## New Features (2025)

### Real-Time Game Status Display
- **Status Polling**: UI polls game execution status every 500ms
- **Live Updates**: Shows current action ("Requesting action from P1", "Waiting for response", etc.)
- **Prompt Inspection**: Click "View Query Sent" to see exact LLM prompts and responses
- **Visual Indicators**: Icons and colors indicate execution state (💭 querying, ⏳ waiting, ⚙️ applying)

**New API Endpoints**:
- `GET /games/{game_id}/status` - Get current execution status
- `GET /games/{game_id}/prompts/{request_id}` - Retrieve stored LLM prompt details

**Implementation Files**:
- Backend: [src/mmllm/game/loop.py](src/mmllm/game/loop.py), [src/mmllm/web/api/routes_games.py](src/mmllm/web/api/routes_games.py)
- Frontend: [src/mmllm/web/ui/static/js/modules/status.js](src/mmllm/web/ui/static/js/modules/status.js), [src/mmllm/web/ui/templates/game.html](src/mmllm/web/ui/templates/game.html)
