# Code Conventions

## Python Style
- **Python 3.11+** features encouraged
- **Type hints** on all function signatures
- **Pydantic models** for all data structures
- **async/await** for I/O operations
- **f-strings** for string formatting

## Naming
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Player IDs: `p1`, `p2`, etc.
- Game IDs: `game_{uuid}` or `game_{timestamp}`
- Event IDs: `evt_{uuid8}`

## Module Organization
```
src/mmllm/{domain}/
    __init__.py      # Public exports
    {feature}.py     # Implementation
```

## Pydantic Patterns
```python
from pydantic import BaseModel, Field

class MyModel(BaseModel):
    required_field: str
    optional_field: Optional[str] = None
    with_default: int = Field(default=0, ge=0)

    model_config = ConfigDict(frozen=True)  # immutable
```

## FastAPI Patterns
```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/resource", tags=["resource"])

@router.post("/")
async def create_resource(req: CreateRequest) -> ResourceResponse:
    ...
```

## Error Handling
- Raise `HTTPException` for API errors
- Use `ValueError` for invalid arguments
- Use `RuntimeError` for unexpected states
- Log errors with context before raising

## Event Sourcing
- All state changes emit events
- Events are immutable facts
- State rebuilt by replaying events
- Never mutate state without emitting event

## Testing
- Test files: `tests/test_{module}.py`
- Use pytest fixtures for setup
- Test happy path and error cases
- Mock LLM calls in unit tests

## Configuration
- YAML for complex config (`configs/*.yaml`)
- JSON for data (`configs/party.json`)
- `.env` for secrets (never commit)
- Environment variables for deployment

## Logging
- Use Python `logging` module
- Log level from `MMLLM_LOG_LEVEL` env var
- Include context (game_id, player_id) in log messages

## File Paths
- Use `pathlib.Path` not string concatenation
- Repo root determined at runtime
- Relative paths from repo root
