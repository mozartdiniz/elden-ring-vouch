#!/usr/bin/env bash
# Development server. Deployment runs uvicorn directly, without --reload.
#
#   ./run.sh                      localhost only, the default and the safe one
#   HOST=0.0.0.0 ./run.sh         reachable from the LAN — see README before doing this
#
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

if [ "$HOST" != "127.0.0.1" ] && [ -z "${ACCESS_TOKEN:-}" ]; then
  echo "refusing to listen on $HOST without ACCESS_TOKEN set." >&2
  echo "this endpoint spends model calls and has no other authentication." >&2
  echo "  ACCESS_TOKEN=\$(openssl rand -hex 16) HOST=$HOST ./run.sh" >&2
  exit 1
fi

exec .venv/bin/uvicorn app:app --reload --host "$HOST" --port "$PORT"
