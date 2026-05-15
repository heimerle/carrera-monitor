# Contracts — Carrera Digital Telemetry Dashboard MVP

This project's "external interfaces" are not HTTP endpoints; they are:

1. The **CLI** (`cli.md`) — what hobbyists type to run the system.
2. The **JSONL event log format** (`event-log.md`) — what tools downstream of this project consume.
3. The **State snapshot file** (`state-snapshot.md`) — what the Streamlit dashboard reads.
4. The **`CarreraAdapter` Python Protocol** (`carrera-adapter.md`) — what mock and live clients implement.

Each contract file below is the source of truth for its surface; implementations and tests MUST match.
