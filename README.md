# Carrera Digital Telemetry Dashboard

A self-hosted Python dashboard for the Carrera Digital 132/124 AppConnect
Bluetooth adapter. Capture live telemetry, persist it as canonical JSONL,
and watch a live Streamlit dashboard — all from one process.

## Highlights

- **Mock-first.** Develop and demo without any hardware via
  `python -m src.main --mock`.
- **Canonical event schema.** Every producer (mock or live) emits the
  same Pydantic `TelemetryEvent` — replay/analytics tools never need to
  understand raw Bluetooth frames.
- **Atomic persistence.** State snapshots use tmp + `os.replace`; the
  Streamlit dashboard polls a JSON file and never imports the
  Bluetooth stack.
- **Resilient.** Auto-reconnect with explicit `connection_state`
  transitions, drop-oldest backpressure on the event bus, and graceful
  SIGINT/SIGTERM shutdown.
- **Supervisor-based BLE lifecycle.** A long-running
  `BluetoothConnectionSupervisor` owns live connect/disconnect/reconnect
  behavior outside Streamlit reruns.

## Quickstart (mock mode, no hardware)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.main --mock
# In another shell, the Streamlit dashboard auto-opens on
# http://localhost:8501 (or use --no-dashboard to skip).
```

See [specs/main/quickstart.md](specs/main/quickstart.md) for the full
5-minute walkthrough.

## Hardware setup

For live mode you also need
[`carreralib`](https://github.com/tkem/carreralib):

```bash
pip install carreralib
python -m src.main --mac AA:BB:CC:DD:EE:FF
```

> ⚠️ The current live adapter is gated behind research item **R-001**
> (`tasks.md` T027). Run `--mock` until the hardware integration is
> verified end-to-end.

See [docs/troubleshooting.md](docs/troubleshooting.md) for Bluetooth
permission, scan, and reconnect issues.

## Configuration

YAML (defaults shown in [config.example.yaml](config.example.yaml)):

```yaml
bluetooth:
  scan_timeout_seconds: 10
  connect_timeout_seconds: 15
  reconnect_interval_seconds: 5
  max_reconnect_interval_seconds: 30
  reconnect_backoff_seconds: [1, 2, 5, 10, 20, 30]
  stale_timeout_seconds: 10
  reconnect_on_stale: true
  allow_manual_connect: true
  allow_manual_disconnect: true
  prefer_scan_device_object: true
  mac_address: null         # null = scan
logging:
  directory: logs
  csv_laps_enabled: true
  debug_raw_enabled: false  # also dumps raw frames as "raw" events
dashboard:
  enabled: true
  refresh_interval_ms: 200
  port: 8501
cars:
  count: 6
```

Pass with `--config path/to/config.yaml`. CLI flags override.

### Bluetooth controls in Streamlit

The **Settings** page now acts as a UI proxy:

- it writes connect/disconnect/scan/retry requests to
  `data/runtime_settings.json`
- the runtime process executes those commands in the supervisor
- status is read from `logs/state.json` (`connection` section)

Displayed Bluetooth status includes desired state, selected device,
last-seen telemetry timestamp, reconnect attempts, and latest error.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the producer →
bus → consumers diagram and the component contract.

## Race Management

The pipeline now persists configured races to a local SQLite database
(`data/carrera_dashboard.sqlite3`) and surfaces them in three additional
Streamlit pages: **Race Management**, **Race Reports**, and **Settings**.
Create a race (mode `fixed_laps` or `fixed_duration`), start it, and the
running telemetry feed automatically records laps. Finished races can be
**Repeated** with one click (drivers + mode preserved, no historical
data) and exported to CSV (per-driver standings + per-lap detail).

- Walkthrough: [specs/001-race-management/quickstart.md](specs/001-race-management/quickstart.md)
- Streamlit entry point: `streamlit run src/app.py -- --mock` (or simply
  let `python -m src.main --mock` spawn it for you).
- **Schema reset policy**: the project has no Alembic migrations yet
  (deferred per research item R-103). When the schema changes, stop the
  app, delete `data/carrera_dashboard.sqlite3` (plus the `-wal`/`-shm`
  sidecars), and relaunch — `init_db()` will recreate the tables.

## Known Limitations

- Single-process. The dashboard is a Streamlit subprocess of the
  producer; cross-machine viewing requires SSH tunneling.
- No replay tool yet. The JSONL format is stable but `tools/replay.py`
  is post-MVP (see roadmap).
- No WebSocket/REST surface — only `state.json` polling.

## Roadmap

- `tools/replay.py` to drive the dashboard from a recorded JSONL.
- WebSocket/REST API for headless dashboards and remote viewers.
- Bluetooth sniffer mode for adapter reverse engineering (R-008).
- Analytics overlays (sector times, fuel projections).
- OBS browser-source overlay.

## Testing

```bash
pytest -q
ruff check src tests
mypy src
```

The suite covers event schema, supervisor/service lifecycle behavior,
mock client, storage, state manager, and adapter contracts.
