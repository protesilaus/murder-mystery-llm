# API Reference

Base URL: `http://127.0.0.1:8000`

## Game Management (`/games`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/games/` | Create new game with players and agent type |
| GET | `/games/` | List all active game IDs |
| GET | `/games/{game_id}` | Get full game state + events |
| POST | `/games/{game_id}/advance` | Advance to next phase |
| POST | `/games/{game_id}/resolve_votes` | Tally votes and eliminate |
| POST | `/games/{game_id}/auto` | Run game to completion |
| POST | `/games/{game_id}/round` | Run single round (night→day→vote) |
| POST | `/games/{game_id}/action` | Execute one agent action |
| POST | `/games/{game_id}/interject` | Inject narrator message |
| POST | `/games/{game_id}/rewind` | Restore to event index |

### Create Game Request
```json
{
  "player_ids": ["p1", "p2", "p3", "p4", "p5", "p6"],
  "agent_type": "ollama",  // or "scripted"
  "model": "llama3.2"
}
```

## Agent Testing (`/agents`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/agents/prompts` | Get all prompt templates |
| POST | `/agents/ollama/test` | Test Ollama connectivity |
| POST | `/agents/ollama/raw` | Test raw prompt against Ollama |

### Raw Prompt Test
```json
{
  "system": "You are a helpful assistant.",
  "user": "Hello, who are you?",
  "model": "llama3.2"
}
```

## Party Management (`/party`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/party/` | Load current party config |
| POST | `/party/` | Save party config |
| POST | `/party/generate` | Generate display names via LLM |

### Party Config Format
```json
{
  "party": {
    "players": [
      {"player_id": "p1", "display_name": "Alice", "character_name": "", "score": 0}
    ]
  }
}
```

## Run Artifacts (`/runs`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/runs/` | List run directories |
| GET | `/runs/{run_id}/events` | Get events for a run |

## UI Pages

| Path | Template | Purpose |
|------|----------|---------|
| `/` | `index.html` | Control room dashboard |
| `/game/{game_id}` | `game.html` | Live game viewer |
| `/test` | `test.html` | Prompt testing interface |

## Health Check

| Method | Endpoint | Response |
|--------|----------|----------|
| GET | `/health` | `{"status": "ok"}` |
