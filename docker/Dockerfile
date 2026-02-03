FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/
COPY src /app/src

RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn>=0.25" "pydantic>=2.6" "pyyaml>=6.0.1"

ENV PYTHONPATH=/app/src

CMD ["uvicorn", "mmllm.web.main:app", "--host", "0.0.0.0", "--port", "8000"]
