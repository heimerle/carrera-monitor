# Troubleshooting — Carrera Telemetry Dashboard

Common issues when running the live (Bluetooth) pipeline.

## "carreralib is not installed"

The default install only pulls dependencies needed for **mock mode**.
For live mode install the upstream library in your virtualenv:

```bash
pip install -e .[live]
# or:
pip install carreralib
```

This also pulls `bleak` (BLE backend, transitively `pyobjc-*` on macOS)
and `pyserial` (for direct-USB Carrera Control Units).

## Discovering your Control Unit's address

Run a one-shot scan and exit:

```bash
python -m src.main --scan
```

Sample output on macOS (the address is a CoreBluetooth UUID, not a real
MAC):

```
Scanning for Carrera Control Units (this may take a few seconds)...
Found 1 device(s):
  EA20D98C-3B4E-2B7C-AB40-CFAC35F05AD6      Control_Unit

To use the first Control Unit, run: carrera-monitor --mac <address>
```

Pass that address back via `--mac`, or write it to `config.yaml`:

```yaml
bluetooth:
  mac_address: EA20D98C-3B4E-2B7C-AB40-CFAC35F05AD6
```

## Bluetooth scan finds nothing

1. Confirm the Carrera AppConnect unit is powered on and not paired with
   the official iOS/Android app (it can only host one connection at a time).
2. On macOS, give your terminal Bluetooth permission in **System
   Settings → Privacy & Security → Bluetooth**.
3. Retry with a longer scan timeout in `config.yaml`:
   ```yaml
   bluetooth:
     scan_timeout_seconds: 30
   ```

## Repeated `reconnecting` connection_state events

The `CarreraClientRunner` will keep retrying every
`bluetooth.reconnect_interval_seconds` (default 5 s) and emit a
`connection_state` event each time. Check:

- AppConnect within Bluetooth range
- No other app is currently connected to the unit
- The MAC address (if passed via `--mac`) is correct

## Dashboard shows "stale data"

The Streamlit dashboard reads `logs/state.json`. If the producer process
has stopped writing for more than 5 × `dashboard.refresh_interval_ms`,
a stale banner appears. Check:

1. The producer (`python -m src.main --mock` or live) is still running.
2. The producer's log dir matches the dashboard's `dashboard.state_file`
   (defaults under the same `logging.directory`).

## JSONL file rotation / disk pressure

JSONL files use `carrera-{YYYYMMDD-HHMMSS}-{pid}.jsonl`. They are
**not** auto-rotated. If you run long sessions, prune `logs/` manually
or symlink `logs/` to a larger volume.

## "Permission denied" writing logs

The pipeline auto-creates the configured log directory. If running under
a restricted user, ensure the directory is writable, or override via
`config.yaml`:

```yaml
logging:
  directory: /tmp/carrera-logs
```
