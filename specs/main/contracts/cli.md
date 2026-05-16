# CLI Contract

Entry point: `python -m src.main`

## Synopsis

```
python -m src.main [--mock] [--config PATH] [--mac MAC] [--log-dir PATH]
                   [--no-dashboard] [--log-level LEVEL] [--debug-raw]
python -m src.main --scan [--config PATH] [--log-level LEVEL]
```

## Flags

| Flag | Type | Default | Description |
|---|---|---|---|
| `--mock` | bool | `false` | Use the mock telemetry generator; ignore `--mac` and any BLE scan. |
| `--config PATH` | path | `./config.yaml` if present, else built-in defaults | YAML config file. |
| `--mac MAC` | str | from config | Bypass BLE scan, connect to this MAC. Combined with `--mock`, the precedence defined by FR-225 (002-race-controls) applies: `--mock` wins, `--mac` is ignored. |
| `--log-dir PATH` | path | from config (`./logs`) | Override log directory. |
| `--no-dashboard` | bool | `false` | Do not auto-launch Streamlit dashboard. |
| `--log-level LEVEL` | enum | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `--debug-raw` | bool | `false` | Enable raw-frame passthrough events (FR-013). Overrides `logging.debug_raw_enabled`. Off by default to keep JSONL files lean. |
| `--scan` | bool | `false` | Scan for Carrera Control Units via BLE/serial, print one line per discovered device (`<MAC>\t<name>`) to **stdout**, then exit `0`. No telemetry pipeline is started; no dashboard is launched. Intended for one-shot adapter discovery before a real session. |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Clean shutdown (SIGINT/SIGTERM after graceful flush) or successful `--scan` exit. |
| `1` | Configuration error (invalid YAML, invalid values). |
| `3` | Unrecoverable runtime error (with structured error logged). |

## Stdout / Stderr

- All structured logs → stderr as one JSON object per line.
- Stdout is reserved for human-readable banner + dashboard URL.
- Tools that consume logs MUST read stderr.

## Signals

- `SIGINT` / `SIGTERM`: enter graceful shutdown; flush storage; close adapter; exit 0 within 5 s.
- `SIGHUP`: reserved for future config reload (not implemented in MVP; logs a warning).
