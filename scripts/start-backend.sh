#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

uv sync --project backend --dev
exec uv run --project backend uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

