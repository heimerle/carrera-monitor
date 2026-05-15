# Contracts

This directory holds the interface contracts that the race-management module exposes to the rest of the application.

- [race-service.md](./race-service.md) — `RaceService` method signatures, exceptions, pre/post-conditions.
- [reporting-service.md](./reporting-service.md) — `ReportingService` methods and report payload shapes.
- [database-schema.md](./database-schema.md) — `CREATE TABLE` shapes (informational; produced by `Base.metadata.create_all()`).

UI contracts (page layout and required widgets) are specified inline in [../spec.md](../spec.md) under FR-127…FR-130 and the user stories' Acceptance Scenarios; they do not need a separate contract file at this stage.
