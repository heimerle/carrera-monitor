# Quickstart — Race Management

## 1. Install / upgrade dependencies

```bash
pip install -e ".[dev]"      # picks up the new SQLAlchemy>=2.0 entry in requirements.txt
```

## 2. Configure

Copy `config.example.yaml` to `config.yaml` (if you haven't) and ensure the new sections exist:

```yaml
database:
  url: "sqlite:///./data/carrera_dashboard.sqlite3"
  echo: false

race_management:
  persist_all_events: true
  allow_edit_running_race: false
  default_race_status_after_create: "draft"
  recover_running_race: false
```

The `data/` directory is created automatically on first run.

## 3. Launch (mock mode — no hardware needed)

```bash
streamlit run src/app.py -- --mock
```

The browser opens with four tabs:

- **Dashboard** — the existing live leaderboard (unchanged).
- **Race Management** — create / edit / start / pause / repeat races.
- **Race Reports** — view, save, and CSV-export reports for any past race.
- **Settings** — read-only view of effective config.

## 4. Create + run + report a race (10-lap, 2 drivers)

1. Open **Race Management → "New Race"**.
2. Enter:
   - Name: `Friday Night 10`
   - Mode: `Fixed Laps`
   - Lap target: `10`
   - Driver count: `2`
   - Driver 1 (car 1): `Alice`
   - Driver 2 (car 2): `Bob`
3. Click **Save** → the race appears in the list with status `draft`.
4. Click **Start** → status flips to `running`; the **Dashboard** tab begins recording laps for cars 1 and 2 into the DB.
5. Once each car has crossed the line 10 times, the race auto-finishes (status `finished`, `finished_at` set, summary auto-persisted).
6. Open **Race Reports → Friday Night 10** to see standings, per-driver stats, and a CSV download button.

## 5. Repeat the race

1. In **Race Management**, click **Repeat** next to `Friday Night 10`.
2. A new draft race `Friday Night 10 (copy)` appears with the same config and drivers, zero laps.
3. Optionally rename, then click **Start**.

## 6. Run the tests

```bash
pytest
```

All 52 existing tests must still pass, plus the new ones for repository / service / reporting / runner / repeat. ("52" is the pre-001 baseline; the total drifts as later slices land — see CI on `main` for the current count.)

## 7. Live mode

Switch to live Carrera hardware via the existing flag:

```bash
streamlit run src/app.py -- --live --device-address AA:BB:CC:DD:EE:FF
```

Race management works identically — only the event source changes.
