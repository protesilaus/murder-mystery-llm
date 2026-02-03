#!/usr/bin/env bash
set -euo pipefail

uvicorn mmllm.web.main:app --reload --host 0.0.0.0 --port 8000
