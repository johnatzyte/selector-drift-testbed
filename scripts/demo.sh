#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8811}"

if command -v ss >/dev/null && ss -tln 2>/dev/null | grep -qE "[:.]${PORT}[[:space:]]"; then
  echo "Port ${PORT} is already in use. Set PORT=<other> and retry." >&2
  exit 1
fi

PORT="$PORT" exec uv run --locked python -m shop
