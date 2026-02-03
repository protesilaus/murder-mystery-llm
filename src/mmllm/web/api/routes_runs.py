"""Tournament run routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_runs():
    return {"runs": []}


@router.post("/")
def start_run():
    return {"run_id": "run_001"}
