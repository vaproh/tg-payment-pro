default:
    @just --list

run:
    uv run main.py

webhook:
    uv run uvicorn webhooks.server:app --host 0.0.0.0 --port 8000

books:
    uv run uvicorn webhooks.server:app --host 0.0.0.0 --port 8000

test:
    uv run pytest tests/ -v

install:
    uv sync
