#!/usr/bin/env bash
# Development server. Deployment runs uvicorn directly, without --reload.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a
exec .venv/bin/uvicorn app:app --reload --port "${PORT:-8000}"
