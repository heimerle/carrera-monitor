#!/usr/bin/env bash
set -euo pipefail

# Launches the Carrera telemetry pipeline (src.main), which now serves the
# RacePulse 132 dashboard at http://localhost:<dashboard.port> (default 8501).
# The dashboard renders live Control-Unit telemetry read from logs/state.json
# via its /api/state endpoint. Pass --no-dashboard to skip it. The old
# Streamlit UI (src/app.py, src/dashboard.py) is no longer launched.

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
