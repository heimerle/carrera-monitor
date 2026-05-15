# Quickstart — Carrera Digital Telemetry Dashboard MVP

Goal: get a live dashboard with simulated telemetry running in under 5 minutes, no hardware required.

## Prerequisites

- Python 3.11+
- macOS / Linux / Windows
- Git

## 1. Clone & install

```bash
git clone <this-repo>
cd carrera-monitor
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Run in mock mode

```bash
python -m src.main --mock
```

Expected behavior:

- Stdout prints a banner and the dashboard URL (default `http://localhost:8501`).
- A new JSONL log file appears under `./logs/`.
- A Streamlit tab opens (or you open the URL manually) showing per-car cards, lap counters, fuel, and a recent-event stream.

## 3. Verify telemetry

```bash
tail -f logs/carrera-*.jsonl | head -n 20
```

You should see one valid JSON object per line, including `lap`, `fuel`, `race_state`, and occasionally `pitlane` events.

## 4. Configure (optional)

Copy the example config and edit:

```bash
cp config.example.yaml config.yaml
```

Useful settings:
- `cars.count`: 1–6 mock cars.
- `dashboard.refresh_interval_ms`: 500–2000 ms.
- `logging.csv_laps_enabled`: also write a per-lap CSV.

Restart with `python -m src.main --mock --config config.yaml`.

## 5. Run with real hardware (when available)

1. Power on the Carrera AppConnect adapter.
2. Either let the app scan (`python -m src.main`) or set `bluetooth.mac_address` in `config.yaml` and run `python -m src.main --mac <MAC>`.
3. Connection state on the dashboard should cycle `scanning → connecting → connected`.
4. To test reconnect: toggle the adapter off and on; state should reach `reconnecting → connected` automatically within `2 × reconnect_interval_seconds`.

## 6. Run tests

```bash
pytest -q
```

Expected: all tests pass (event model, storage, mock client, state manager).

## 7. Stop

`Ctrl+C` in the pipeline terminal. Storage flushes and the process exits with code 0 within 5 seconds.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Dashboard shows "initializing" forever | Pipeline not running or wrong log dir | Verify `python -m src.main --mock` is running and `logging.directory` matches. |
| `No module named carreralib` in mock mode | `carreralib` import attempted at top level | Make sure you're on `--mock`; `carreralib` is only imported by the live client. |
| Streamlit fails to bind to port | Port in use | Set `dashboard.port` to another value. |
| Adapter found but no events | Adapter not in race mode / `carreralib` API mismatch | Check stderr logs; see TODOs in `src/carrera_client.py`. |
