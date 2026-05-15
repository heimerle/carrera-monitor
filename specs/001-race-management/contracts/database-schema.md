# Contract: Database Schema

Authoritative DDL is produced by `Base.metadata.create_all(engine)` in `src/database.py`. The shapes below are informational and must match the SQLAlchemy models in `src/models.py`.

```sql
CREATE TABLE races (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              VARCHAR(120) NOT NULL CHECK (length(trim(name)) > 0),
    mode              VARCHAR(20)  NOT NULL CHECK (mode IN ('fixed_laps','fixed_duration')),
    lap_target        INTEGER      CHECK (lap_target IS NULL OR lap_target > 0),
    duration_seconds  INTEGER      CHECK (duration_seconds IS NULL OR duration_seconds > 0),
    driver_count      INTEGER      NOT NULL CHECK (driver_count BETWEEN 1 AND 6),
    status            VARCHAR(20)  NOT NULL DEFAULT 'draft'
                                   CHECK (status IN ('draft','ready','running','paused','finished','cancelled')),
    notes             TEXT,
    source_race_id    INTEGER      REFERENCES races(id) ON DELETE SET NULL,
    created_at        DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at        DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    started_at        DATETIME,
    finished_at       DATETIME
);
CREATE INDEX ix_races_status           ON races(status);
CREATE INDEX ix_races_created_at       ON races(created_at);
CREATE INDEX ix_races_source_race_id   ON races(source_race_id);

CREATE TABLE race_drivers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id      INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    car_id       INTEGER NOT NULL CHECK (car_id BETWEEN 1 AND 6),
    driver_name  VARCHAR(80) NOT NULL CHECK (length(trim(driver_name)) > 0),
    created_at   DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    UNIQUE (race_id, car_id)
);
CREATE INDEX ix_race_drivers_race_id ON race_drivers(race_id);

CREATE TABLE race_laps (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id        INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    car_id         INTEGER NOT NULL CHECK (car_id BETWEEN 1 AND 6),
    driver_name    VARCHAR(80) NOT NULL,
    lap_number     INTEGER NOT NULL CHECK (lap_number > 0),
    lap_time_ms    INTEGER NOT NULL CHECK (lap_time_ms > 0),
    timestamp_iso  DATETIME NOT NULL,
    created_at     DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    UNIQUE (race_id, car_id, lap_number)
);
CREATE INDEX ix_race_laps_race_car ON race_laps(race_id, car_id, lap_number);

CREATE TABLE race_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id        INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    timestamp_iso  DATETIME NOT NULL,
    event_type     VARCHAR(40) NOT NULL,
    car_id         INTEGER CHECK (car_id IS NULL OR car_id BETWEEN 1 AND 6),
    payload_json   TEXT NOT NULL,
    raw_data_json  TEXT,
    created_at     DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);
CREATE INDEX ix_race_events_race_type ON race_events(race_id, event_type);

CREATE TABLE race_reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id       INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    report_type   VARCHAR(40) NOT NULL,
    payload_json  TEXT NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);
CREATE INDEX ix_race_reports_race_type ON race_reports(race_id, report_type);
```

Pragmas applied per connection (in `src/database.py` `@event.listens_for(engine, "connect")` hook):

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous   = NORMAL;
PRAGMA foreign_keys  = ON;
```
