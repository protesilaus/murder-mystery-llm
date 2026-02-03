"""FastAPI app entry."""

from pathlib import Path
import shutil

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mmllm.web.api.routes_agents import router as agents_router
from mmllm.web.api.routes_games import router as games_router
from mmllm.web.api.routes_party import router as party_router
from mmllm.web.api.routes_runs import router as runs_router

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "ui" / "templates")

app = FastAPI(title="Murder Mystery LLM")

app.mount("/static", StaticFiles(directory=BASE_DIR / "ui" / "static"), name="static")

app.include_router(games_router, prefix="/games", tags=["games"])
app.include_router(runs_router, prefix="/runs", tags=["runs"])
app.include_router(agents_router, prefix="/agents", tags=["agents"])
app.include_router(party_router, prefix="/party", tags=["party"])


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "page_title": "Control Room",
        },
    )


@app.get("/game/{game_id}", response_class=HTMLResponse)
def game_view(request: Request, game_id: str):
    return templates.TemplateResponse(
        "game.html",
        {
            "request": request,
            "page_title": f"Game {game_id}",
            "game_id": game_id,
            "page_class": "game-page",
            "content_class": "game-content",
        },
    )


@app.get("/test", response_class=HTMLResponse)
def test_view(request: Request):
    return templates.TemplateResponse(
        "test.html",
        {
            "request": request,
            "page_title": "Prompt Test",
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def _init_run_dir() -> None:
    runs_root = Path.cwd() / "runs"
    if runs_root.exists():
        shutil.rmtree(runs_root)
    runs_root.mkdir(parents=True, exist_ok=True)
    run_dir = runs_root / "run_current"
    run_dir.mkdir(parents=True, exist_ok=True)
    app.state.run_dir = run_dir
    app.state.event_offsets = {}
