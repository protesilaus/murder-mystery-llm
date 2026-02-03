# Murder Mystery LLM

Mafia-style social deduction game simulation with LLM agents.

## Quickstart
- Configure environment variables in .env (see .env.example)
- Install dependencies using your preferred tool (uv, pip, poetry)
- Run the API server: `uvicorn mmllm.web.main:app --reload`

## Structure
- configs: YAML configuration files
- src/mmllm: core library and services
- scripts: utilities for running and exporting data
- runs: output logs and artifacts
- tests: unit tests
- docker: deployment assets
