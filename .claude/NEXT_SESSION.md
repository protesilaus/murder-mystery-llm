# Next Coding Session

## Recently Completed (2025-02-03)

### ✅ Real-Time Game Status Display
Implemented a comprehensive status display system showing what's happening during game execution:

**What was built:**
- Backend execution status tracking (`ExecutionStatus`, `GameStatus`)
- Status updates at key points in game loop (requesting, waiting, applying)
- LLM prompt capture and storage system
- Two new API endpoints: `/games/{id}/status` and `/games/{id}/prompts/{request_id}`
- Frontend status polling (500ms intervals)
- Status display UI with icons and colors
- "View Query Sent" modal to inspect LLM prompts

**Files modified:**
- Backend: `types.py`, `state.py`, `loop.py`, `local_client.py`, `routes_games.py`
- Frontend: `game.html`, `main.css`, `app.js`, new `status.js` module

**Testing needed:**
- [ ] Test with live Ollama game to verify status updates work
- [ ] Test prompt modal displays correctly
- [ ] Verify polling stops on page navigation
- [ ] Check behavior with rapid button clicks

---

## Tasks for Next Session

### High Priority

1. **Optimize LLM Prompt Token Usage & Fix Information Leakage**
   - Current player prompts are ~2,800-3,200 tokens each
   - **CRITICAL**: Remove other players' personality controls from public_state (breaks immersion - players shouldn't see opponents' deception/risk scores)
   - Implement transcript windowing (last 5-8 messages only)
   - Consolidate duplicate constraints sections
   - Round float precision to 2 decimals
   - Remove `social_ap` for other players (only show their own)
   - Target: Reduce to ~1,500-1,800 tokens per prompt
   - **Impact**: Fixes game design issue + saves 50-70% of LLM costs

2. **Increase Player Conversation Diversity**
   - Current issue: Players converge on similar phrases ("Has anyone noticed suspicious behavior?")
   - Explore techniques to make conversations more varied and natural
   - Possible approaches:
     - Add temperature/top_p variation per player
     - Include more specific personality-driven prompt instructions
     - Add "avoid repeating recent phrases" constraint
     - Inject unique player backgrounds/motivations
     - Use few-shot examples showing diverse conversation styles
     - Implement prompt techniques like "respond differently than other players"
   - **Goal**: Make 8-player conversations feel less robotic and more dynamic

3. **Real-Time Vote Display**
   - Show votes as they are cast during voting phase
   - Display vote tally and who voted for whom
   - Possible approaches:
     - Extend existing status polling to include vote state
     - Add vote visualization (e.g., "p3 → p4", "p5 → p4", "p7 → p1")
     - Show live vote count per player
     - Highlight when majority/plurality is reached
   - **Goal**: Make voting phase more engaging and transparent

### Medium Priority

1. **OpenAI Integration**
   - Add OpenAI API client support alongside existing Ollama
   - Test if GPT-4/GPT-4-turbo performs better than local models
   - Configuration toggle in `configs/app.yaml`
   - Compare conversation quality, diversity, strategic play

2. **Capture/Stocks Mechanic**
   - Add "capture" action as alternative to elimination
   - Captured player goes in stocks (can't act that night)
   - Town can test if night kills stop when specific player is captured
   - Requires: New action type, vote variant, phase logic

3. **Bunking System (Alibi Mechanic)**
   - Players can choose to "bunk together" at night
   - Each player knows if their bunkmate left during the night
   - Creates alibi verification and trust-building
   - Requires: New night action, observation messages, strategy implications

4. **Persistent Player Profiles**
   - Save player "cards" as JSON files (`data/players/{player_id}.json`)
   - Store: name, personality values, game history, win/loss record
   - Track performance across multiple matches
   - Load existing personalities or generate new ones
   - **Goal**: See which personality types succeed at different roles

5. **Evidence/Clue System**
   - Give each player randomized attributes (hair color, clothing, height, etc.)
   - At end of each day, reveal one random clue about the murderer
   - Examples: "The murderer has red hair", "The murderer was wearing a blue jacket"
   - Multiple players may share attributes (not direct identification)
   - **Goal**: Create deductive reasoning opportunities for LLMs

6. **Color Tagging System (Collaborative Detection)**
   - Players can "tag" other players with a color (limited palette: 3-5 colors)
   - If a tagged player commits murder, their color(s) are found at the scene
   - Example: "Blue and red paint found at the crime scene"
   - Requires coordination: players must share who they tagged with what color
   - Creates strategic gameplay:
     - Town must organize tagging strategy ("I'll use blue on p3")
     - Murderer can see they're tagged and might change behavior
     - Multiple tags on same player = stronger evidence
   - Requires: New day action, tracking system, evidence reveal logic
   - **Goal**: Force collaboration and create concrete detection mechanism

### Low Priority / Future Ideas

- Consider persisting prompts to disk for debugging/replay
- Add performance metrics (LLM response time tracking)
- Upgrade to WebSocket for true real-time updates (if polling becomes a bottleneck)
- Show streaming token generation from LLM

---

## Known Issues

- None currently identified

---

## Current System State

**Server:** Ready to run with `uvicorn mmllm.web.main:app --host 127.0.0.1 --port 8000 --reload`

**Configuration Files:**
- `configs/app.yaml` - App settings
- `configs/game_rules.yaml` - Game parameters
- `configs/prompts.yaml` - LLM prompt templates
- `configs/party.json` - Player roster
- `configs/gametypes/*.json` - Game type definitions

**Recent Changes:** All changes from real-time status display feature are committed to git working tree (not yet committed)

---

## Quick Reference

**Key API Endpoints (NEW):**
- `GET /games/{game_id}/status` - Current execution status
- `GET /games/{game_id}/prompts/{request_id}` - Retrieve stored prompt

**Key Files for Status System:**
- Backend: [src/mmllm/game/loop.py](../src/mmllm/game/loop.py) - Status updates
- Backend: [src/mmllm/web/api/routes_games.py](../src/mmllm/web/api/routes_games.py) - API endpoints
- Frontend: [src/mmllm/web/ui/static/js/modules/status.js](../src/mmllm/web/ui/static/js/modules/status.js) - Polling logic
- Frontend: [src/mmllm/web/ui/templates/game.html](../src/mmllm/web/ui/templates/game.html) - Status UI

**Testing Commands:**
```bash
# Run server
uvicorn mmllm.web.main:app --host 127.0.0.1 --port 8000 --reload

# Run tests
pytest

# Run specific test
pytest tests/test_engine.py::test_function_name -v

# Lint
ruff check src/
```

---

## Notes

*Add any additional notes or context for the next session here*
