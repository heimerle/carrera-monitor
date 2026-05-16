#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

if [[ $# -eq 0 ]]; then
  # Force persisted runtime mode to live when no explicit CLI arguments are given.
  "$PYTHON_BIN" - <<'PY'
from src.services.runtime_settings import set_mock_mode

set_mock_mode(False)
PY
fi

exec "$PYTHON_BIN" -m src.main "$@"
