# Architecture — Carrera Telemetry Dashboard

## High-Level Topology

```
                      +---------------------+
                      |  CarreraAdapter     |
                      |  (Mock | Live)      |
                      +----------+----------+
                                 | TelemetryEvent
                                 v
                         +-------+-------+
                         |   EventBus    |
                         |  (in-proc     |
                         |   asyncio)    |
                         +---+-------+---+
                             |       |
              storage queue  |       |  state queue
              (8192)         |       |  (1024)
                             v       v
                  +----------+--+  +-+------------+
                  | JsonlEvent  |  | StateManager |
                  | Writer      |  | (writes      |
                  | (+CSV laps) |  |  state.json) |
                  +-------------+  +------+-------+
                                          |
                                          | atomic write
                                          v
                                   +------+-------+
                                   |  state.json  |
                                   +------+-------+
                                          |
                                          | mtime poll (Streamlit)
                                          v
                                   +------+-------+
                                   |  dashboard   |
                                   |  subprocess  |
                                   +--------------+
```

## Components

| Component | Module | Responsibility |
| --- | --- | --- |
| Adapter | `src/carrera_client.py` | Bluetooth seam. Lazy-imports `carreralib`. Mock implementation in `src/mock_client.py`. |
| Translator | `src/carrera_client.translate_raw_frame` | **Only** place that knows raw frame shapes. Used by both mock and live. |
| EventBus | `src/event_bus.py` | Bounded async pub/sub with drop-oldest backpressure. |
| StateManager | `src/state_manager.py` | Reduces events into a small `StateSnapshot`, writes `state.json` atomically. |
| Storage | `src/storage.py` | Async JSONL writer (batched ≤ 250 ms) + optional CSV lap writer. |
| Dashboard | `src/dashboard.py` | Streamlit subprocess. Reads `state.json` only, never imports BLE. |
| CLI | `src/main.py` | Wires it all together with SIGINT/SIGTERM graceful shutdown. |

## Event Schema

The canonical event is `src.event_model.TelemetryEvent` (frozen Pydantic
model). Allowed payload keys per `event_type` are whitelisted in
`_ALLOWED_PAYLOAD_KEYS` — unknown keys are rejected. See
[`specs/main/contracts/event-log.md`](../specs/main/contracts/event-log.md)
for the full per-type contract.

## Persistence Guarantees

- **JSONL** (`logs/carrera-{YYYYMMDD-HHMMSS}-{pid}.jsonl`): every event
  emitted by the producer is written. 100 % parse rate against
  `TelemetryEvent.model_validate_json` is a tested invariant
  (`tests/test_storage.py::test_500_event_session_roundtrip`).
- **CSV** (`logs/laps-...csv`): one row per `lap` event with
  `car_id,lap_number,lap_time_ms,timestamp_iso`. Disabled if
  `logging.csv_enabled = false`.
- **state.json**: written atomically via tmp file + `os.replace` so
  partial reads from the dashboard never see a torn snapshot.

## Replay (Planned)

Replay is **not** in MVP scope. The JSONL format is the contract: any
future `tools/replay.py` can stream lines back through `EventBus` to
re-drive the same `StateManager` + dashboard with zero changes to the
core pipeline. See [event-log.md](../specs/main/contracts/event-log.md)
for the field contract that a replayer must respect.
